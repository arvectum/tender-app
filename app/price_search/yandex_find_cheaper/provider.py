from __future__ import annotations

from decimal import Decimal

from app.config import get_settings
from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate, PriceSearchProvider
from app.price_search.normalization import normalize_delivery_price, normalize_quantity, normalize_region, normalize_url
from app.price_search.query_builder import build_search_query
from app.price_search.relevance import calculate_offer_relevance
from app.price_search.yandex_find_cheaper.browser_agent import YandexBrowserAgent


class YandexFindCheaperProvider(PriceSearchProvider):
    provider_name = "yandex"

    def __init__(self) -> None:
        self.agent = YandexBrowserAgent()
        self.settings = get_settings()

    def search_offers(self, item: PurchaseItem) -> list[MarketOfferCandidate]:
        query = build_search_query(item)
        rows, warnings = self.agent.search(query=query, limit=10)

        candidates: list[MarketOfferCandidate] = []
        for row in rows:
            unit_price = row.get("unit_price")
            if unit_price is None:
                continue

            quantity, quantity_flags = normalize_quantity(row.get("available_quantity"))
            delivery_price, delivery_flags = normalize_delivery_price(row.get("delivery_price"))
            region, region_flags = normalize_region(row.get("region") or self.settings.price_search_region)

            candidate = MarketOfferCandidate(
                provider=self.provider_name,
                purchase_item_id=item.id,
                title=str(row.get("title") or item.item_name),
                url=normalize_url(str(row.get("url") or "")),
                seller_name=row.get("seller_name") or None,
                region=region,
                unit_price=Decimal(str(unit_price)),
                available_quantity=quantity,
                delivery_price=delivery_price,
                delivery_days=None,
                raw_payload=row,
                risk_flags=sorted(set(quantity_flags + delivery_flags + region_flags)),
                item_name=item.item_name,
            )
            relevance = calculate_offer_relevance(item, candidate)
            candidate.is_relevant = relevance.is_relevant
            candidate.relevance_score = relevance.score
            candidate.risk_flags = sorted(set(candidate.risk_flags + relevance.risk_flags))
            candidates.append(candidate)

        # Fail closed: when search is blocked/captcha/no parsable rows,
        # return no candidates so caller marks item as needs_manual_price_search.
        # This avoids persisting synthetic zero-price offers that inflate margin.
        if warnings and not candidates:
            return []

        return candidates
