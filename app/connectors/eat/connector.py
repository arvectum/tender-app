from __future__ import annotations

from app.connectors.base import BasePurchaseConnector, ParsedPurchase
from app.connectors.eat.api_client import EatApiClient
from app.connectors.eat.browser_fallback import EatBrowserFallback
from app.connectors.eat.parser import parse_purchase_payload
from app.utils.logging import get_file_logger


connectors_logger = get_file_logger("connectors.eat.connector", "connectors.log")


class EatConnector(BasePurchaseConnector):
    source = "eat"

    def __init__(self) -> None:
        self.api_client = EatApiClient()
        self.browser_fallback = EatBrowserFallback()

    def fetch_active_purchases(
        self,
        status: str = "Прием предложений",
        limit: int | None = None,
    ) -> list[ParsedPurchase]:
        connectors_logger.info("eat fetch start | status=%s limit=%s", status, limit)
        records, warnings, errors = self.api_client.fetch_purchases(status=status, limit=limit)

        for warning in warnings:
            connectors_logger.warning("eat api warning: %s", warning)
        for error in errors:
            connectors_logger.error("eat api error: %s", error)

        if not records:
            connectors_logger.info("eat switching to browser fallback")
            records, fb_warnings, fb_errors = self.browser_fallback.fetch_cards(status=status, limit=limit)
            for warning in fb_warnings:
                connectors_logger.warning("eat fallback warning: %s", warning)
            for error in fb_errors:
                connectors_logger.error("eat fallback error: %s", error)

        parsed: list[ParsedPurchase] = []
        for raw in records:
            try:
                parsed.append(parse_purchase_payload(raw, source=self.source))
            except Exception as exc:  # noqa: BLE001
                connectors_logger.exception("eat parse error: %s", exc)

        if limit is not None:
            parsed = parsed[:limit]

        connectors_logger.info("eat fetch finished | parsed=%s", len(parsed))
        return parsed
