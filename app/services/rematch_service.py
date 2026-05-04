from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import MarketOffer, PurchaseItem
from app.price_search.base import MarketOfferCandidate
from app.price_search.relevance import calculate_offer_relevance
from app.services.business_rules_service import BusinessRulesService
from app.services.supplier_service import SupplierService, normalize_supplier_name


def rematch_offers(
    session: Session,
    purchase_id: int | None = None,
    item_id: int | None = None,
) -> int:
    settings = get_settings()
    rules = BusinessRulesService(session)
    supplier_service = SupplierService(session)
    threshold = rules.get_typed("MIN_OFFER_RELEVANCE_SCORE", settings.min_offer_relevance_score, float)

    stmt = select(PurchaseItem).options(selectinload(PurchaseItem.attributes))
    if purchase_id is not None:
        stmt = stmt.where(PurchaseItem.purchase_id == purchase_id)
    if item_id is not None:
        stmt = stmt.where(PurchaseItem.id == item_id)
    items = session.scalars(stmt).all()

    updated = 0
    for item in items:
        offers = session.scalars(select(MarketOffer).where(MarketOffer.purchase_item_id == item.id)).all()
        for offer in offers:
            supplier = supplier_service.resolve(offer.seller_name or offer.supplier_name)
            supplier_status = supplier.status if supplier is not None else "unknown"

            candidate = MarketOfferCandidate(
                provider=offer.provider,
                purchase_item_id=item.id,
                title=offer.offer_title or offer.item_name,
                url=offer.offer_url,
                seller_name=offer.seller_name or offer.supplier_name,
                region=offer.region,
                unit_price=Decimal(str(offer.unit_price)),
                available_quantity=Decimal(str(offer.available_quantity)),
                delivery_price=Decimal(str(offer.delivery_price)) if offer.delivery_price is not None else None,
                delivery_days=offer.delivery_days,
                is_relevant=offer.is_relevant,
                relevance_score=float(offer.relevance_score or Decimal("0")),
                raw_payload=offer.raw_payload,
                risk_flags=list(offer.risk_flags or []),
                item_name=offer.item_name,
                comment=offer.comment,
            )
            relevance = calculate_offer_relevance(
                item=item,
                offer=candidate,
                supplier_status=supplier_status,
                min_threshold=threshold,
            )
            is_relevant = relevance.is_relevant and relevance.score >= threshold
            if offer.manual_override_exclude:
                is_relevant = False
            if offer.manual_override_include:
                is_relevant = True

            offer.is_relevant = is_relevant
            offer.relevance_score = Decimal(str(relevance.score))
            offer.match_score = Decimal(str(relevance.score))
            offer.match_reasons_json = relevance.reasons
            offer.match_risk_flags_json = relevance.risk_flags
            offer.matched_fields_json = relevance.matched_fields
            offer.mismatched_fields_json = relevance.mismatched_fields
            offer.hard_reject_reason = relevance.hard_reject_reason
            offer.seller_name_normalized = normalize_supplier_name(offer.seller_name or offer.supplier_name or "")
            offer.supplier_status = supplier_status
            offer.supplier_id = supplier.id if supplier is not None else None
            updated += 1

    session.commit()
    return updated
