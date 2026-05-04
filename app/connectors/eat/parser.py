from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.connectors.base import ParsedPurchase, ParsedPurchaseItem


def parse_purchase_payload(raw: dict[str, Any], source: str = "eat") -> ParsedPurchase:
    items_raw = raw.get("items") or raw.get("positions") or raw.get("purchaseItems") or []
    parsed_items: list[ParsedPurchaseItem] = []
    for item_raw in items_raw:
        if not isinstance(item_raw, dict):
            continue
        try:
            parsed_items.append(parse_item_payload(item_raw))
        except Exception:
            continue

    external_id = _pick(raw, ["externalId", "id", "purchaseId", "number", "announcementId"]) or ""

    return ParsedPurchase(
        source=source,
        external_id=str(external_id),
        title=_pick(raw, ["title", "name", "subject", "purchaseName"]) or f"EAT {external_id}",
        url=_pick(raw, ["url", "link", "href"]) or _build_purchase_url(external_id),
        status=_pick(raw, ["status", "statusName", "state"]),
        region=_pick(raw, ["region", "deliveryRegion", "regionName"]),
        customer_name=_pick(raw, ["customerName", "customer", "organizationName", "buyerName"]),
        submission_deadline=_parse_datetime(_pick(raw, ["submissionDeadline", "deadline", "endDate", "bidsEndDate"])),
        commission_fee_amount=_parse_decimal(_pick(raw, ["commissionFeeAmount", "commission"])),
        security_amount=_parse_decimal(_pick(raw, ["securityAmount", "deposit"])),
        max_total_price=_parse_decimal(_pick(raw, ["maxTotalPrice", "startPrice", "sum", "initialPrice"])),
        created_at_source=_parse_datetime(_pick(raw, ["createdAt", "publishDate", "creationDate"])),
        items=parsed_items,
        raw_payload=raw,
    )


def parse_item_payload(raw: dict[str, Any]) -> ParsedPurchaseItem:
    name = _pick(raw, ["name", "itemName", "title", "description"]) or ""
    if not name:
        raise ValueError("item name required")

    quantity = _parse_decimal(_pick(raw, ["quantity", "qty", "count", "amount"])) or Decimal("1")

    return ParsedPurchaseItem(
        position_external_id=_pick(raw, ["positionExternalId", "positionId", "id", "itemId"]),
        name=name,
        description=_pick(raw, ["description", "itemDescription", "details"]),
        okpd2=_pick(raw, ["okpd2", "okpd2Code", "classifier"]),
        quantity=quantity,
        unit=_pick(raw, ["unit", "measure", "unitName"]),
        max_unit_price=_parse_decimal(_pick(raw, ["maxUnitPrice", "unitPrice", "price"])),
        max_total_price=_parse_decimal(_pick(raw, ["maxTotalPrice", "totalPrice", "sum"])),
        delivery_region=_pick(raw, ["deliveryRegion", "region"]),
        delivery_address=_pick(raw, ["deliveryAddress", "address", "deliveryPlace"]),
        delivery_terms=_pick(raw, ["deliveryTerms", "deliveryConditions", "terms"]),
        raw_payload=raw,
    )


def _pick(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    cleaned = "".join(ch for ch in normalized if ch in "0123456789.-")
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _build_purchase_url(external_id: str) -> str | None:
    if not external_id:
        return None
    return f"https://agregatoreat.ru/purchases/announcement/{external_id}"
