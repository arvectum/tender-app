from __future__ import annotations

import csv
import json
import re
import subprocess
import zipfile
from urllib.parse import urlparse

import requests
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
        price = _pick_first_price(
            row,
            [
                "tender_unit_price_ref",
                "unit_price",
                "offered_unit_price",
                "market_price",
                "min_price",
                "final_price",
                "price",
            ],
        )
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
    input_rows_count = len(market_rows)
    excluded_non_goods_count = 0
    auction_items_cache: dict[str, list[dict[str, object]]] = {}

    for row in market_rows:
        purchase_id = str(row.get("purchase_external_id", "")).strip()
        item_name = str(row.get("item_name", "")).strip()
        offer_title = str(row.get("offer_title", "")).strip()
        offer_source_url = str(row.get("offer_source_url", "")).strip()
        found_offer_unit_price = _pick_first_price(
            row,
            [
                "found_offer_unit_price",
                "offered_unit_price",
                "unit_price",
                "effective_unit_price",
                "market_price",
                "min_price",
                "final_price",
                "price",
            ],
        )
        market_unit_price = _pick_first_price(
            row,
            [
                "market_unit_price",
                "unit_price",
                "offered_unit_price",
                "market_price",
                "found_offer_unit_price",
                "effective_unit_price",
                "min_price",
                "final_price",
                "price",
            ],
        )
        if market_unit_price is None and offer_source_url:
            resolved = _resolve_price_from_offer_source(
                purchase_id=purchase_id,
                item_name=item_name,
                offer_source_url=offer_source_url,
                cache=auction_items_cache,
            )
            if resolved is not None:
                market_unit_price = resolved
                if found_offer_unit_price is None:
                    found_offer_unit_price = resolved

        if _is_non_goods_item(item_name):
            excluded_non_goods_count += 1
            diag_rows.append(
                {
                    "purchase_external_id": purchase_id,
                    "attachment_path": "",
                    "tz_extraction_status": "skipped",
                    "tz_extraction_reason": "excluded_non_goods",
                    "tz_text_len": 0,
                    "tz_match_type": "skipped",
                    "strict_full_match": False,
                    "tz_overlap_ratio": 0.0,
                    "margin_pct": None,
                    "decision_status": "excluded",
                    "decision_reason": "excluded_non_goods",
                }
            )
            continue

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

        strict_full_match = _is_strict_attribute_match(tz_text=tz_text, offer_text=f"{item_name} {offer_title}") or (
            bool(tz_tokens) and tz_tokens.issubset(all_offer_tokens)
        )
        overlap = (len(tz_tokens & all_offer_tokens) / len(tz_tokens)) if tz_tokens else 0.0
        fallback_non_product_match = False
        if not strict_full_match and _is_non_product_tz_text(tz_text):
            fallback_non_product_match = bool(item_tokens or title_tokens)

        match_type = "none"
        if strict_full_match or fallback_non_product_match:
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
        elif market_unit_price is None or found_offer_unit_price is None:
            decision_status = "reject"
            decision_reason = "missing_search_price"
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
                "found_offer_unit_price": found_offer_unit_price,
                "offer_source_url": offer_source_url,
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
        "input_rows": input_rows_count,
        "report_rows": len(report_rows),
        "excluded_non_goods_rows": excluded_non_goods_count,
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


def _is_non_goods_item(item_name: str) -> bool:
    text = _normalize_ru_text(item_name)
    non_goods_markers = (
        "монтаж",
        "демонтаж",
        "ремонт",
        "обслуживание",
        "установка",
        "наладка",
        "проектирование",
        "услуги",
        "работы",
    )
    return any(marker in text for marker in non_goods_markers)


def _normalize_ru_text(text: str) -> str:
    prepared = text.lower().replace("ё", "е")
    prepared = prepared.replace("\xa0", " ")
    prepared = re.sub(r"[^a-zа-я0-9]+", " ", prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"\s+", " ", prepared)
    return prepared.strip()


def _extract_model_tokens(text: str) -> set[str]:
    prepared = re.sub(r"[^a-zа-я0-9\-/]+", " ", text.lower().replace("ё", "е"), flags=re.IGNORECASE)
    candidates = prepared.split()
    return {
        token
        for token in candidates
        if len(token) >= 4 and any(ch.isalpha() for ch in token) and any(ch.isdigit() for ch in token)
    }


def _extract_numbers(text: str) -> set[str]:
    return set(re.findall(r"\d{2,}", text))


def _extract_units(text: str) -> set[str]:
    units_map = {
        "шт": "шт",
        "штук": "шт",
        "штука": "шт",
        "штуки": "шт",
        "ед": "шт",
        "pcs": "шт",
        "pc": "шт",
        "компл": "компл",
        "комплект": "компл",
        "комплекта": "компл",
    }
    tokens = _normalize_ru_text(text).split()
    return {units_map[t] for t in tokens if t in units_map}


def _is_strict_attribute_match(*, tz_text: str, offer_text: str) -> bool:
    tz_norm = _normalize_ru_text(tz_text)
    offer_norm = _normalize_ru_text(offer_text)
    if not tz_norm or not offer_norm:
        return False

    offer_compact = offer_text.lower().replace("ё", "е").replace(" ", "")
    tz_models = _extract_model_tokens(tz_text)
    if tz_models and not all(model in offer_compact for model in tz_models):
        return False

    tz_numbers = _extract_numbers(tz_norm)
    offer_numbers = _extract_numbers(offer_norm)
    long_tz_numbers = {n for n in tz_numbers if len(n) >= 5}
    if long_tz_numbers and not long_tz_numbers.issubset(offer_numbers):
        return False

    tz_units = _extract_units(tz_norm)
    offer_units = _extract_units(offer_norm)
    if tz_units and offer_units and not tz_units.issubset(offer_units):
        return False

    return bool(tz_models or long_tz_numbers or (tz_units and tz_numbers))


def _is_non_product_tz_text(text: str) -> bool:
    norm = _normalize_ru_text(text)
    if not norm:
        return False

    tokens = norm.split()
    if len(tokens) < 5:
        return False

    if _extract_model_tokens(norm):
        return False
    if any(len(n) >= 5 for n in _extract_numbers(norm)):
        return False

    noise_markers = {
        "инструкция",
        "регистрация",
        "пользователя",
        "организации",
        "электронной",
        "подписи",
        "требования",
        "порядок",
        "документооборот",
    }
    overlap = sum(1 for t in tokens if t in noise_markers)
    return overlap >= 2


def _resolve_price_from_offer_source(
    *,
    purchase_id: str,
    item_name: str,
    offer_source_url: str,
    cache: dict[str, list[dict[str, object]]],
) -> float | None:
    auction_id = _extract_auction_id(offer_source_url)
    if not auction_id:
        return None

    items = cache.get(auction_id)
    if items is None:
        items = _fetch_auction_items(auction_id)
        cache[auction_id] = items
    if not items:
        return None

    exact_norm = _normalize_ru_text(item_name)
    for item in items:
        if _normalize_ru_text(str(item.get("name", ""))) == exact_norm:
            price = _to_float(item.get("costPerUnit"))
            if price is not None:
                return price

    for item in items:
        price = _to_float(item.get("costPerUnit"))
        if price is not None:
            return price
    return None


def _extract_auction_id(url: str) -> str | None:
    try:
        path_parts = [p for p in urlparse(url).path.split("/") if p]
    except Exception:
        return None
    if len(path_parts) >= 2 and path_parts[0] == "auction" and path_parts[1].isdigit():
        return path_parts[1]
    return None


def _fetch_auction_items(auction_id: str) -> list[dict[str, object]]:
    api_url = f"https://zakupki.mos.ru/newapi/api/Auction/Get?auctionId={auction_id}"
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(api_url, timeout=20)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []
    items = payload.get("items")
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    return []


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


def _pick_first_price(row: dict[str, object], fields: list[str]) -> float | None:
    for field in fields:
        price = _to_float(row.get(field))
        if price is not None:
            return price
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
