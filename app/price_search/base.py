from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models import PurchaseItem


@dataclass
class MarketOfferCandidate:
    provider: str
    purchase_item_id: int | None
    title: str
    url: str | None
    seller_name: str | None
    region: str | None
    unit_price: Decimal
    available_quantity: Decimal
    delivery_price: Decimal | None
    delivery_days: int | None
    is_relevant: bool = True
    relevance_score: float = 1.0
    raw_payload: dict[str, Any] | None = None
    risk_flags: list[str] = field(default_factory=list)
    item_name: str | None = None
    comment: str | None = None
    delivery_type: str | None = None
    delivery_price_type: str | None = None
    pickup_available: bool | None = None
    delivery_unknown: bool = False
    min_order_quantity: int | None = None
    package_quantity: int | None = None
    match_score: float | None = None
    match_reasons: list[str] = field(default_factory=list)
    match_risk_flags: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)
    mismatched_fields: list[str] = field(default_factory=list)
    hard_reject_reason: str | None = None


@dataclass
class OfferRelevanceResult:
    is_relevant: bool
    score: float
    reasons: list[str]
    risk_flags: list[str]
    hard_reject: bool = False
    matched_fields: list[str] = field(default_factory=list)
    mismatched_fields: list[str] = field(default_factory=list)
    hard_reject_reason: str | None = None


class PriceSearchProvider:
    provider_name: str = "base"

    def search_offers(self, item: PurchaseItem) -> list[MarketOfferCandidate]:
        raise NotImplementedError
