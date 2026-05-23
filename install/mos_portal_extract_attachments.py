from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import requests
from playwright.sync_api import sync_playwright


DOWNLOAD_RE = re.compile(r"/newapi/api/FileStorage/Download\?id=(\d+)", re.IGNORECASE)
TZ_NAME_RE = re.compile(r"(тз|техническ|задани|spec|специф|описани)", re.IGNORECASE)
GENERIC_NAME_RE = re.compile(r"(регистрац|эп|инструкц|памятк|guide|widget|attach\.svg)", re.IGNORECASE)


@dataclass
class Candidate:
    name: str
    url: str


def _sanitize_filename(name: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9А-Яа-я._-]+", "_", name).strip("._")
    return value or fallback


def _file_id(url: str) -> str | None:
    m = DOWNLOAD_RE.search(url)
    if m:
        return m.group(1)
    q = parse_qs(urlparse(url).query)
    if "id" in q and q["id"]:
        return str(q["id"][0])
    return None


def _extract_candidates(hrefs: Iterable[str]) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    for href in hrefs:
        if not href:
            continue
        if not DOWNLOAD_RE.search(href):
            continue
        fid = _file_id(href)
        if not fid or fid in seen:
            continue
        seen.add(fid)
        out.append(Candidate(name=f"Download_{fid}.pdf", url=href))
    return out


def _is_likely_tz_name(name: str) -> bool:
    lower = name.lower()
    if GENERIC_NAME_RE.search(lower):
        return False
    return bool(TZ_NAME_RE.search(lower))


def _pdf_text_len(data: bytes) -> int:
    try:
        from pypdf import PdfReader
    except Exception:
        return 0
    try:
        import io

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return len(text.strip())
    except Exception:
        return 0


def _download_file(session: requests.Session, url: str, referer: str) -> tuple[bytes, str]:
    resp = session.get(url, timeout=60, allow_redirects=True, headers={"Referer": referer})
    resp.raise_for_status()
    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/html" in ctype:
        raise RuntimeError("html_instead_of_file")
    return resp.content, ctype


def run(purchase_ids: list[str], output_dir: Path, manifest_path: Path, reasons_path: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    reason_rows: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        for pid in purchase_ids:
            card_url = f"https://zakupki.mos.ru/purchase/{pid}"
            try:
                page.goto(card_url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(3500)
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            except Exception as exc:  # noqa: BLE001
                reason_rows.append({"purchase_external_id": pid, "reason": f"card_open_failed:{exc}", "card_url": card_url})
                continue

            candidates = _extract_candidates(hrefs)
            if not candidates:
                reason_rows.append({"purchase_external_id": pid, "reason": "no_purchase_scoped_filestorage_links", "card_url": card_url})
                continue

            # requests without ambient proxy env to avoid random proxy html pages
            sess = requests.Session()
            sess.trust_env = False
            sess.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
            for c in context.cookies(card_url):
                sess.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

            pid_dir = output_dir / pid
            pid_dir.mkdir(parents=True, exist_ok=True)
            kept = 0
            for idx, cand in enumerate(candidates, start=1):
                fid = _file_id(cand.url) or str(idx)
                fname = _sanitize_filename(cand.name, f"file_{fid}.pdf")
                out_path = pid_dir / fname
                try:
                    data, ctype = _download_file(sess, cand.url, card_url)
                except Exception as exc:  # noqa: BLE001
                    reason_rows.append({"purchase_external_id": pid, "reason": f"download_failed:{exc}", "attachment_url": cand.url})
                    continue

                size = len(data)
                if size < 1024:
                    reason_rows.append({"purchase_external_id": pid, "reason": f"too_small:{size}", "attachment_url": cand.url})
                    continue

                text_len = _pdf_text_len(data) if "pdf" in ctype or out_path.suffix.lower() == ".pdf" else 0
                name_hint_ok = _is_likely_tz_name(fname)
                if text_len == 0 and not name_hint_ok:
                    reason_rows.append({
                        "purchase_external_id": pid,
                        "reason": "rejected_non_tz_or_empty_text",
                        "attachment_url": cand.url,
                        "file_name": fname,
                    })
                    continue

                out_path.write_bytes(data)
                manifest_rows.append({"purchase_external_id": pid, "attachment_path": str(out_path)})
                kept += 1

            if kept == 0:
                reason_rows.append({"purchase_external_id": pid, "reason": "all_candidates_rejected", "card_url": card_url})

        browser.close()

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["purchase_external_id", "attachment_path"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    fields = sorted({k for r in reason_rows for k in r.keys()} or {"purchase_external_id", "reason"})
    with reasons_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reason_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output-dir", default="exports/mos_portal_attachments_fix")
    parser.add_argument("--manifest", default="exports/small_tender_attachments_manifest_fix.csv")
    parser.add_argument("--reasons", default="exports/mos_portal_attachments_unavailable_reasons_fix.csv")
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.source_csv).open(encoding="utf-8")))
    ids = sorted({str(r.get("purchase_external_id", "")).strip() for r in rows if str(r.get("purchase_external_id", "")).strip()})
    run(ids[: args.limit], Path(args.output_dir), Path(args.manifest), Path(args.reasons))


if __name__ == "__main__":
    main()
