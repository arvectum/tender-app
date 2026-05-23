from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import requests

TZ_NAME_RE = re.compile(r"(тз|техническ|задани|spec|специф|описани)", re.IGNORECASE)
GENERIC_NAME_RE = re.compile(r"(регистрац|эп|инструкц|памятк|guide|widget|attach\.svg)", re.IGNORECASE)


@dataclass
class Candidate:
    file_id: int
    name: str


def _sanitize_filename(name: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9А-Яа-я._-]+", "_", name).strip("._")
    return value or fallback


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


def _docx_text_len(data: bytes) -> int:
    try:
        import io
        from zipfile import ZipFile
        import xml.etree.ElementTree as ET

        with ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
        root = ET.fromstring(xml)
        text = "".join((el.text or "") for el in root.iter() if el.text)
        return len(text.strip())
    except Exception:
        return 0


def _extract_text_len(name: str, data: bytes, ctype: str) -> int:
    suffix = Path(name).suffix.lower()
    if "pdf" in ctype or suffix == ".pdf":
        return _pdf_text_len(data)
    if suffix == ".docx":
        return _docx_text_len(data)
    return 0


def _download_file(session: requests.Session, file_id: int) -> tuple[bytes, str]:
    url = "https://zakupki.mos.ru/newapi/api/FileStorage/Download"
    resp = session.get(url, timeout=60, allow_redirects=True, params={"id": file_id})
    resp.raise_for_status()
    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/html" in ctype:
        raise RuntimeError("html_instead_of_file")
    return resp.content, ctype


def _auction_files(session: requests.Session, auction_id: str) -> list[Candidate]:
    url = "https://zakupki.mos.ru/newapi/api/Auction/Get"
    r = session.get(url, params={"auctionId": auction_id}, timeout=60)
    if r.status_code != 200:
        return []
    try:
        payload = r.json()
    except Exception:
        return []
    files = payload.get("files") or []
    out: list[Candidate] = []
    seen_ids: set[int] = set()
    for f in files:
        try:
            fid = int(f.get("id"))
        except Exception:
            continue
        if fid in seen_ids:
            continue
        seen_ids.add(fid)
        name = str(f.get("name") or f.get("fileName") or f"Download_{fid}")
        out.append(Candidate(file_id=fid, name=name))
    return out


def run(purchase_ids: list[str], output_dir: Path, manifest_path: Path, reasons_path: Path, examples_path: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    reason_rows: list[dict[str, str]] = []
    example_rows: list[dict[str, str]] = []

    sess = requests.Session()
    sess.trust_env = False
    sess.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "*/*"})

    for pid in purchase_ids:
        candidates = _auction_files(sess, pid)
        if not candidates:
            reason_rows.append({"purchase_external_id": pid, "reason": "auction_get_no_files"})
            continue

        # prioritize TZ-like names first
        candidates = sorted(candidates, key=lambda c: (0 if _is_likely_tz_name(c.name) else 1, c.name.lower()))

        kept = 0
        pid_dir = output_dir / pid
        pid_dir.mkdir(parents=True, exist_ok=True)

        for cand in candidates:
            fname = _sanitize_filename(cand.name, f"file_{cand.file_id}")
            out_path = pid_dir / fname

            try:
                data, ctype = _download_file(sess, cand.file_id)
            except Exception as exc:  # noqa: BLE001
                reason_rows.append({"purchase_external_id": pid, "reason": f"download_failed:{exc}", "file_id": str(cand.file_id), "file_name": cand.name})
                continue

            size = len(data)
            if size < 512:
                reason_rows.append({"purchase_external_id": pid, "reason": f"too_small:{size}", "file_id": str(cand.file_id), "file_name": cand.name})
                continue

            text_len = _extract_text_len(cand.name, data, ctype)
            name_hint_ok = _is_likely_tz_name(cand.name)

            # strict: keep only files likely to be TZ, and require extractable text for pdf/docx
            suffix = Path(cand.name).suffix.lower()
            if not name_hint_ok:
                reason_rows.append({"purchase_external_id": pid, "reason": "rejected_non_tz_name", "file_id": str(cand.file_id), "file_name": cand.name})
                continue
            if suffix in {".pdf", ".docx"} and text_len == 0:
                reason_rows.append({"purchase_external_id": pid, "reason": "rejected_empty_text", "file_id": str(cand.file_id), "file_name": cand.name})
                continue

            out_path.write_bytes(data)
            sha16 = hashlib.sha256(data).hexdigest()[:16]
            manifest_rows.append({"purchase_external_id": pid, "attachment_path": str(out_path)})
            example_rows.append(
                {
                    "purchase_external_id": pid,
                    "attachment_path": str(out_path),
                    "size": str(size),
                    "sha256_16": sha16,
                    "tz_text_len": str(text_len),
                    "file_id": str(cand.file_id),
                    "file_name": cand.name,
                }
            )
            kept += 1

        if kept == 0:
            reason_rows.append({"purchase_external_id": pid, "reason": "all_candidates_rejected"})

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["purchase_external_id", "attachment_path"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    fields = sorted({k for r in reason_rows for k in r.keys()} or {"purchase_external_id", "reason"})
    with reasons_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(reason_rows)

    with examples_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["purchase_external_id", "attachment_path", "size", "sha256_16", "tz_text_len", "file_id", "file_name"],
        )
        writer.writeheader()
        writer.writerows(example_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output-dir", default="exports/mos_portal_attachments_fix")
    parser.add_argument("--manifest", default="exports/small_tender_attachments_manifest_fix.csv")
    parser.add_argument("--reasons", default="exports/mos_portal_attachments_unavailable_reasons_fix.csv")
    parser.add_argument("--examples", default="exports/mos_portal_attachments_examples_fix.csv")
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.source_csv).open(encoding="utf-8")))
    ids = sorted({str(r.get("purchase_external_id", "")).strip() for r in rows if str(r.get("purchase_external_id", "")).strip()})
    run(ids[: args.limit], Path(args.output_dir), Path(args.manifest), Path(args.reasons), Path(args.examples))


if __name__ == "__main__":
    main()
