from __future__ import annotations

from app.config import get_settings
from app.matching import match_offer_to_item
from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate, OfferRelevanceResult


def calculate_offer_relevance(
    item: PurchaseItem,
    offer: MarketOfferCandidate,
    supplier_status: str = "unknown",
    min_threshold: float | None = None,
) -> OfferRelevanceResult:
    settings = get_settings()
    threshold = float(getattr(settings, "min_offer_relevance_score", 0.78)) if min_threshold is None else float(min_threshold)
    match = match_offer_to_item(item=item, offer=offer, min_score=threshold, supplier_status=supplier_status)
    return OfferRelevanceResult(
        is_relevant=match.is_match,
        score=match.score,
        reasons=match.reasons,
        risk_flags=match.risk_flags,
        hard_reject=match.hard_reject,
        matched_fields=match.matched_fields,
        mismatched_fields=match.mismatched_fields,
        hard_reject_reason=match.hard_reject_reason,
    )
