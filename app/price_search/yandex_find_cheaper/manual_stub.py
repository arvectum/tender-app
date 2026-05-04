from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.config import get_settings
from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate, PriceSearchProvider
from app.price_search.normalization import normalize_delivery_price, normalize_quantity, normalize_region
from app.price_search.relevance import calculate_offer_relevance


class StubPriceSearchProvider(PriceSearchProvider):
    provider_name = "stub"

    def __init__(self, fixture_path: Path | None = None) -> None:
        settings = get_settings()
        self.fixture_path = fixture_path or (settings.project_root / "fixtures" / "sample_market_offers.json")

    def search_offers(self, item: PurchaseItem) -> list[MarketOfferCandidate]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        candidates: list[MarketOfferCandidate] = []

        for row in payload:
            if str(row.get("item_name", "")).strip().lower() != item.item_name.strip().lower():
                continue

            quantity, quantity_flags = normalize_quantity(row.get("available_quantity"))
            delivery_price, delivery_flags = normalize_delivery_price(row.get("delivery_price"))
            region, region_flags = normalize_region(row.get("region") or row.get("region_code"))

            candidate = MarketOfferCandidate(
                provider=self.provider_name,
                purchase_item_id=item.id,
                title=row.get("offer_title") or row.get("item_name") or item.item_name,
                url=row.get("offer_url"),
                seller_name=row.get("seller_name") or row.get("supplier_name"),
                region=region,
                unit_price=Decimal(str(row.get("unit_price"))),
                available_quantity=quantity,
                delivery_price=delivery_price,
                delivery_days=row.get("delivery_days"),
                is_relevant=bool(row.get("is_relevant", True)),
                relevance_score=float(row.get("relevance_score", 1.0)),
                raw_payload=row,
                risk_flags=sorted(set(quantity_flags + delivery_flags + region_flags)),
                item_name=row.get("item_name") or item.item_name,
                comment=row.get("comment"),
            )
            relevance = calculate_offer_relevance(item, candidate)
            if row.get("is_relevant") is None:
                candidate.is_relevant = relevance.is_relevant
            candidate.relevance_score = float(row.get("relevance_score", relevance.score))
            candidate.risk_flags = sorted(set(candidate.risk_flags + relevance.risk_flags))

            candidates.append(candidate)

        return candidates
