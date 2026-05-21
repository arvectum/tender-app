from __future__ import annotations

import csv
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


@dataclass
class AttachmentExtractionResult:
    purchase_external_id: str
    source_path: str
    status: str
    reason: str | None
    text: str


def generate_small_tender_report(
    *,
    market_csv: Path,
    tender_ref_csv: Path,
    out_csv: Path,
    out_xlsx: Path,
    diagnostics_csv: Path,
    attachments_manifest_csv: Path | None = None,
) -> dict[str, int]:
    market_rows = _read_csv(market_csv)
    ref_rows = _read_csv(tender_ref_csv)

    ref_price_by_purchase: dict[str, float] = {}
    for row in ref_rows:
        pid = str(row.get("purchase_external_id", "")).strip()
        price = _to_float(row.get("unit_price"))
        if not pid or price is None:
            continue
        prev = ref_price_by_purchase.get(pid)
        if prev is None or price < prev:
            ref_price_by_purchase[pid] = price

    attachments_by_purchase = _load_attachments_manifest(attachments_manifest_csv)
    extraction_by_purchase: dict[str, AttachmentExtractionResult] = {}
    for purchase_id, paths in attachments_by_purchase.items():
        extraction_by_purchase[purchase_id] = _extract_first_successful_attachment(purchase_id, paths)

    report_rows: list[dict[str, object]] = []
    diag_rows: list[dict[str, object]] = []

    for row in market_rows:
        purchase_id = str(row.get("purchase_external_id", "")).strip()
        item_name = str(row.get("item_name", "")).strip()
        offer_title = str(row.get("offer_title", "")).strip()
        market_unit_price = _to_float(row.get("unit_price") or row.get("found_offer_unit_price") or row.get("effective_unit_price"))

        extraction = extraction_by_purchase.get(purchase_id)
        if extraction is None:
            extraction = AttachmentExtractionResult(
                purchase_external_id=purchase_id,
                source_path="",
                status="failed",
                reason="no_attachment_manifest_entry",
                text="",
            )

        tz_text = extraction.text
        tz_tokens = _tokenize(tz_text)
        item_tokens = _tokenize(item_name)
        title_tokens = _tokenize(offer_title)
        all_offer_tokens = item_tokens | title_tokens

        strict_full_match = bool(tz_tokens) and tz_tokens.issubset(all_offer_tokens)
        overlap = (len(tz_tokens & all_offer_tokens) / len(tz_tokens)) if tz_tokens else 0.0
        match_type = "none"
        if strict_full_match:
            match_type = "full"
        elif overlap >= 0.5:
            match_type = "partial"

        tender_ref_price = ref_price_by_purchase.get(purchase_id)
        margin_pct = None
        if market_unit_price is not None and tender_ref_price and tender_ref_price > 0:
            margin_pct = round(((tender_ref_price - market_unit_price) / tender_ref_price) * 100, 2)

        risk_level = "unknown"
        decision_status = "reject"
        decision_reason = ""

        if extraction.status != "ok":
            decision_status = "reject"
            decision_reason = f"tz_extraction_failed:{extraction.reason or 'unknown'}"
            risk_level = "critical"
        elif match_type != "full":
            decision_status = "reject"
            decision_reason = f"strict_full_match_required:{match_type}"
            risk_level = "critical"
        elif margin_pct is None:
            decision_status = "reject"
            decision_reason = "missing_price_for_margin"
            risk_level = "critical"
        elif margin_pct > 50:
            decision_status = "reject"
            decision_reason = "margin_gt_50_reject"
            risk_level = "critical"
        elif margin_pct > 25:
            decision_status = "high_risk"
            decision_reason = "margin_gt_25_high_risk"
            risk_level = "high"
        else:
            decision_status = "green"
            decision_reason = "strict_full_match_and_margin_ok"
            risk_level = "low"

        report_rows.append(
            {
                **row,
                "tz_extraction_status": extraction.status,
                "tz_extraction_reason": extraction.reason or "",
                "tz_attachment_path": extraction.source_path,
                "tz_text_len": len(tz_text),
                "tz_match_type": match_type,
                "tz_overlap_ratio": round(overlap, 4),
                "strict_full_match": strict_full_match,
                "tender_unit_price_ref": tender_ref_price,
                "market_unit_price": market_unit_price,
                "margin_pct": margin_pct,
                "decision_status": decision_status,
                "risk_level": risk_level,
                "decision_reason": decision_reason,
            }
        )

        diag_rows.append(
            {
                "purchase_external_id": purchase_id,
                "attachment_path": extraction.source_path,
                "tz_extraction_status": extraction.status,
                "tz_extraction_reason": extraction.reason or "",
                "tz_text_len": len(tz_text),
                "tz_match_type": match_type,
                "strict_full_match": strict_full_match,
                "tz_overlap_ratio": round(overlap, 4),
                "margin_pct": margin_pct,
                "decision_status": decision_status,
                "decision_reason": decision_reason,
            }
        )

    _write_csv(out_csv, report_rows)
    _write_xlsx(out_xlsx, report_rows)
    _write_csv(diagnostics_csv, diag_rows)

    return {
        "report_rows": len(report_rows),
        "diagnostics_rows": len(diag_rows),
        "full_match_rows": sum(1 for r in report_rows if r.get("tz_match_type") == "full"),
        "green_rows": sum(1 for r in report_rows if r.get("decision_status") == "green"),
        "high_risk_rows": sum(1 for r in report_rows if r.get("decision_status") == "high_risk"),
        "reject_rows": sum(1 for r in report_rows if r.get("decision_status") == "reject"),
    }


def _load_attachments_manifest(path: Path | None) -> dict[str, list[Path]]:
    if path is None or not path.exists():
        return {}

    rows = _read_csv(path)
    result: dict[str, list[Path]] = {}
    for row in rows:
        purchase_id = str(row.get("purchase_external_id", "")).strip()
        attachment_path = str(row.get("attachment_path", "")).strip()
        if not purchase_id or not attachment_path:
            continue
        result.setdefault(purchase_id, []).append(Path(attachment_path))
    return result


def _extract_first_successful_attachment(purchase_id: str, paths: Iterable[Path]) -> AttachmentExtractionResult:
    errors: list[str] = []
    first_path = ""
    for path in paths:
        first_path = str(path)
        if not path.exists():
            errors.append(f"not_found:{path}")
            continue
        try:
            text = extract_text_from_attachment(path)
            cleaned = _clean_text(text)
            if cleaned:
                return AttachmentExtractionResult(
                    purchase_external_id=purchase_id,
                    source_path=str(path),
                    status="ok",
                    reason=None,
                    text=cleaned,
                )
            errors.append(f"empty_text:{path}")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"extract_error:{path}:{exc}")

    reason = ";".join(errors) if errors else "no_attachments"
    return AttachmentExtractionResult(
        purchase_external_id=purchase_id,
        source_path=first_path,
        status="failed",
        reason=reason,
        text="",
    )


def extract_text_from_attachment(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    raise ValueError(f"unsupported_attachment_type:{suffix}")


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        data = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", data)
    return _clean_text(text)


def _extract_pdf_text(path: Path) -> str:
    pdftotext_bin = "pdftotext"
    check = subprocess.run(["which", pdftotext_bin], capture_output=True, text=True)
    if check.returncode != 0:
        raise RuntimeError("pdftotext_not_installed")

    completed = subprocess.run([pdftotext_bin, "-layout", str(path), "-"], capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"pdftotext_failed:{stderr or 'unknown_error'}")
    return completed.stdout


def _clean_text(text: str) -> str:
    normalized = text.replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _tokenize(text: str) -> set[str]:
    prepared = text.lower().replace("ё", "е")
    prepared = re.sub(r"[^a-zа-я0-9]+", " ", prepared, flags=re.IGNORECASE)
    return {token for token in prepared.split() if len(token) >= 4}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "small_tender_report"

    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])

    wb.save(path)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def build_single_file_manifest(*, source_csv: Path, attachment_path: Path, out_manifest_csv: Path) -> Path:
    rows = _read_csv(source_csv)
    purchase_ids = sorted({str(r.get("purchase_external_id", "")).strip() for r in rows if str(r.get("purchase_external_id", "")).strip()})
    out_manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_manifest_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["purchase_external_id", "attachment_path"])
        writer.writeheader()
        for pid in purchase_ids:
            writer.writerow({"purchase_external_id": pid, "attachment_path": str(attachment_path)})
    return out_manifest_csv
