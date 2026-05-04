from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.connectors.base import ParsedPurchase, ParsedPurchaseItem


def parse_purchase_payload(raw: dict[str, Any], source: str = "mos_portal") -> ParsedPurchase:
    items_raw = _extract_items(raw)
    parsed_items: list[ParsedPurchaseItem] = []
    for item_raw in items_raw:
        try:
            parsed_items.append(parse_item_payload(item_raw))
        except Exception:
            # Keep import resilient: skip malformed item but do not break purchase.
            continue

    title = _pick_first(raw, ["title", "name", "purchaseName", "auctionName", "subject", "displayName"]) or None
    external_id = (
        _pick_first(raw, ["externalId", "id", "purchaseNumber", "sessionId", "auctionId", "number"])
        or ""
    )

    return ParsedPurchase(
        source=source,
        external_id=str(external_id),
        title=str(title) if title else str(external_id),
        url=_build_purchase_url(raw),
        status=_pick_first(raw, ["status", "statusName", "state", "sessionState"]),
        region=_pick_first(raw, ["region", "regionName", "deliveryRegion", "regionTitle"]),
        customer_name=_pick_first(raw, ["customerName", "customer", "organizationName", "buyerName"]),
        submission_deadline=_parse_datetime(_pick_first(raw, ["submissionDeadline", "endDate", "bidsEndDate", "deadline"])),
        commission_fee_amount=_parse_decimal(_pick_first(raw, ["commissionFeeAmount", "commission", "commissionAmount"])),
        security_amount=_parse_decimal(_pick_first(raw, ["securityAmount", "deposit", "bidSecurity"])),
        max_total_price=_parse_decimal(_pick_first(raw, ["maxTotalPrice", "startPrice", "sum", "nmc", "initialPrice"])),
        created_at_source=_parse_datetime(_pick_first(raw, ["createdAt", "publishDate", "creationDate", "startDate"])),
        items=parsed_items,
        raw_payload=raw,
    )


def parse_item_payload(raw: dict[str, Any]) -> ParsedPurchaseItem:
    name = _pick_first(raw, ["name", "itemName", "title", "productName", "description"])
    if not name:
        raise ValueError("item name is required")

    quantity = _parse_decimal(_pick_first(raw, ["quantity", "qty", "count", "amount"])) or Decimal("1")

    return ParsedPurchaseItem(
        position_external_id=_to_string(_pick_first(raw, ["positionExternalId", "id", "positionId", "itemId"])),
        name=str(name),
        description=_pick_first(raw, ["description", "itemDescription", "specification", "details"]),
        okpd2=_pick_first(raw, ["okpd2", "okpd2Code", "ktru", "classifier"]),
        quantity=quantity,
        unit=_pick_first(raw, ["unit", "measure", "unitName", "okei"]),
        max_unit_price=_parse_decimal(_pick_first(raw, ["maxUnitPrice", "unitPrice", "price", "initialUnitPrice"])),
        max_total_price=_parse_decimal(_pick_first(raw, ["maxTotalPrice", "totalPrice", "sum", "positionPrice"])),
        delivery_region=_pick_first(raw, ["deliveryRegion", "region", "deliveryRegionName"]),
        delivery_address=_pick_first(raw, ["deliveryAddress", "address", "deliveryPlace"]),
        delivery_terms=_pick_first(raw, ["deliveryTerms", "deliveryConditions", "terms"]),
        raw_payload=raw,
    )


def _extract_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get("items") or raw.get("positions") or raw.get("purchaseItems") or raw.get("lots")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]

    nested_candidates = [
        raw.get("data"),
        raw.get("result"),
        raw.get("payload"),
        raw.get("auction"),
    ]
    for candidate in nested_candidates:
        if isinstance(candidate, dict):
            nested_items = candidate.get("items") or candidate.get("positions") or candidate.get("purchaseItems")
            if isinstance(nested_items, list):
                return [item for item in nested_items if isinstance(item, dict)]

    return []


def _build_purchase_url(raw: dict[str, Any]) -> str | None:
    direct = _pick_first(raw, ["url", "link", "href"])
    if direct:
        return str(direct)

    external_id = _pick_first(raw, ["externalId", "id", "purchaseNumber", "sessionId", "auctionId", "number"])
    if external_id is None:
        return None

    return f"https://zakupki.mos.ru/auction/{external_id}"


def _pick_first(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        elif isinstance(value, (int, float, Decimal)):
            return str(value)
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


def _to_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
