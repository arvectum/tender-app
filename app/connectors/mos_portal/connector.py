from __future__ import annotations

from typing import Any

from app.connectors.base import BasePurchaseConnector, ParsedPurchase
from app.connectors.mos_portal.api_client import MosPortalApiClient
from app.connectors.mos_portal.browser_fallback import MosPortalBrowserFallback
from app.connectors.mos_portal.parser import parse_purchase_payload
from app.utils.logging import get_file_logger


connectors_logger = get_file_logger("connectors.mos_portal.connector", "connectors.log")


class MosPortalConnector(BasePurchaseConnector):
    source = "mos_portal"

    def __init__(self) -> None:
        self.api_client = MosPortalApiClient()
        self.browser_fallback = MosPortalBrowserFallback()

    def fetch_active_purchases(
        self,
        status: str = "Прием предложений",
        limit: int | None = None,
    ) -> list[ParsedPurchase]:
        connectors_logger.info("mos_portal fetch start | status=%s limit=%s", status, limit)

        raw_records, warnings, errors = self.api_client.fetch_purchases(status=status, limit=limit)
        for warning in warnings:
            connectors_logger.warning("mos_portal api warning: %s", warning)
        for error in errors:
            connectors_logger.error("mos_portal api error: %s", error)

        if not raw_records:
            connectors_logger.info("mos_portal switching to browser fallback")
            fallback_records, fb_warnings, fb_errors = self.browser_fallback.fetch_cards(status=status, limit=limit)
            for warning in fb_warnings:
                connectors_logger.warning("mos_portal fallback warning: %s", warning)
            for error in fb_errors:
                connectors_logger.error("mos_portal fallback error: %s", error)
            raw_records = fallback_records

        parsed: list[ParsedPurchase] = []
        for raw in raw_records:
            try:
                enriched = self.api_client.enrich_with_details(raw)
                parsed_purchase = parse_purchase_payload(enriched, source=self.source)
                parsed.append(parsed_purchase)
            except Exception as exc:  # noqa: BLE001
                external_id = _safe_external_id(raw)
                connectors_logger.exception(
                    "mos_portal parse error | external_id=%s error=%s",
                    external_id,
                    exc,
                )

        if limit is not None:
            parsed = parsed[:limit]

        connectors_logger.info("mos_portal fetch finished | parsed=%s", len(parsed))
        return parsed


def _safe_external_id(raw: dict[str, Any]) -> str:
    for key in ("externalId", "id", "auctionId", "purchaseNumber", "number"):
        value = raw.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return "unknown"
