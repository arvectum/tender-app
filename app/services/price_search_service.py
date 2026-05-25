from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import ItemCostCalculation, MarketOffer, Purchase, PurchaseItem
from app.services.business_rules_service import BusinessRulesService
from app.services.supplier_service import SupplierService, normalize_supplier_name
from app.price_search.base import MarketOfferCandidate
from app.price_search.offer_deduplication import deduplicate_offers
from app.price_search.relevance import calculate_offer_relevance
from app.price_search.yandex_find_cheaper.manual_stub import StubPriceSearchProvider
from app.price_search.yandex_find_cheaper.provider import YandexFindCheaperProvider
from app.utils.logging import get_file_logger
from app.utils.time import utc_now


logger = get_file_logger("price_search", "connectors.log")


@dataclass
class SearchPricesResult:
    mode: str
    processed_items: int = 0
    created_offers: int = 0
    skipped_items: int = 0
    needs_manual_items: int = 0
    needs_manual_reason_counters: dict[str, int] = field(default_factory=dict)
    yandex_stage_counters: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PriceSearchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.business_rules = BusinessRulesService(session)
        self.supplier_service = SupplierService(session)
        self.min_match_score = self.business_rules.get_typed(
            "MIN_OFFER_RELEVANCE_SCORE",
            self.settings.min_offer_relevance_score,
            float,
        )

    def search_prices(
        self,
        mode: str,
        limit: int | None = None,
        purchase_id: int | None = None,
        item_id: int | None = None,
    ) -> SearchPricesResult:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"stub", "manual", "yandex"}:
            raise ValueError(f"Unsupported mode: {mode}")
        if (self.settings.app_mode == "demo" or not self.settings.real_network_enabled) and normalized_mode == "yandex":
            raise ValueError("Real network is disabled in demo mode.")

        items = self._select_target_items(mode=normalized_mode, limit=limit, purchase_id=purchase_id, item_id=item_id)
        result = SearchPricesResult(mode=normalized_mode)

        for item in items:
            try:
                if normalized_mode == "manual":
                    handled = self._process_manual_mode_item(item)
                    result.processed_items += 1
                    result.created_offers += 0
                    if handled == "needs_manual_price_search":
                        result.needs_manual_items += 1
                    continue

                provider = self._provider_for_mode(normalized_mode)
                candidates = provider.search_offers(item)
                diagnostics: dict[str, Any] = {}
                diagnostics_getter = getattr(provider, "get_last_diagnostics", None)
                if callable(diagnostics_getter):
                    diagnostics = diagnostics_getter() or {}
                if not candidates:
                    reason_code = self._derive_needs_manual_reason(diagnostics)
                    reason = reason_code
                    stage_counters = diagnostics.get("stage_counters") if isinstance(diagnostics, dict) else None
                    if isinstance(stage_counters, dict) and stage_counters:
                        reason = f"{reason_code}|stage_counters={stage_counters}"
                        self._merge_int_counters(result.yandex_stage_counters, stage_counters)
                    self._mark_needs_manual(item, reason=reason)
                    result.needs_manual_reason_counters[reason_code] = result.needs_manual_reason_counters.get(reason_code, 0) + 1
                    result.needs_manual_items += 1
                    result.processed_items += 1
                    continue

                for candidate in candidates:
                    if candidate.purchase_item_id is None:
                        candidate.purchase_item_id = item.id
                    if candidate.item_name is None:
                        candidate.item_name = item.item_name

                    supplier = self.supplier_service.resolve(candidate.seller_name)
                    supplier_status = supplier.status if supplier is not None else "unknown"
                    relevance = calculate_offer_relevance(
                        item,
                        candidate,
                        supplier_status=supplier_status,
                        min_threshold=self.min_match_score,
                    )
                    candidate.is_relevant = candidate.is_relevant and relevance.is_relevant
                    candidate.relevance_score = relevance.score if candidate.relevance_score is None else candidate.relevance_score
                    candidate.risk_flags = sorted(set(candidate.risk_flags + relevance.risk_flags))
                    candidate.match_score = relevance.score
                    candidate.match_reasons = relevance.reasons
                    candidate.match_risk_flags = relevance.risk_flags
                    candidate.matched_fields = relevance.matched_fields
                    candidate.mismatched_fields = relevance.mismatched_fields
                    candidate.hard_reject_reason = relevance.hard_reject_reason
                    if candidate.hard_reject_reason:
                        candidate.is_relevant = False

                unique, duplicates = deduplicate_offers(candidates)
                created = self._store_candidates(item, unique)
                created += self._store_candidates(item, duplicates, force_irrelevant=True)
                result.created_offers += created

                if not unique:
                    self._mark_needs_manual(item, reason="all_duplicates_or_invalid")
                    result.needs_manual_reason_counters["all_duplicates_or_invalid"] = result.needs_manual_reason_counters.get("all_duplicates_or_invalid", 0) + 1
                    result.needs_manual_items += 1

                result.processed_items += 1
            except Exception as exc:  # noqa: BLE001
                message = f"item_id={item.id}: {exc}"
                logger.exception("price search item failed | %s", message)
                result.errors.append(message)

        self.session.commit()
        return result

    def _select_target_items(
        self,
        mode: str,
        limit: int | None,
        purchase_id: int | None,
        item_id: int | None,
    ) -> list[PurchaseItem]:
        stmt = select(PurchaseItem).options(
            selectinload(PurchaseItem.purchase),
            selectinload(PurchaseItem.calculations),
            selectinload(PurchaseItem.attributes),
        )
        if purchase_id is not None:
            stmt = stmt.where(PurchaseItem.purchase_id == purchase_id)
        if item_id is not None:
            stmt = stmt.where(PurchaseItem.id == item_id)

        all_items = self.session.scalars(stmt).all()
        target_items: list[PurchaseItem] = []
        for item in all_items:
            offers_count = self.session.scalar(
                select(MarketOffer.id).where(MarketOffer.purchase_item_id == item.id).limit(1)
            )
            has_calc = any(calc.status in {"ok", "insufficient_market_quantity", "no_relevant_offers"} for calc in item.calculations)

            if mode in {"stub", "yandex"}:
                if offers_count is None or not has_calc:
                    target_items.append(item)
            else:
                target_items.append(item)

        target_items.sort(key=lambda row: row.id)
        if limit is not None:
            return target_items[:limit]
        return target_items

    def _provider_for_mode(self, mode: str):
        if mode == "stub":
            return StubPriceSearchProvider()
        if mode == "yandex":
            return YandexFindCheaperProvider()
        raise ValueError(f"Unsupported mode: {mode}")

    def _store_candidates(self, item: PurchaseItem, candidates: list[MarketOfferCandidate], force_irrelevant: bool = False) -> int:
        if not candidates:
            return 0

        created = 0
        for candidate in candidates:
            unit_price = Decimal(str(candidate.unit_price)) if candidate.unit_price is not None else Decimal("0")
            available_quantity = int(Decimal(str(candidate.available_quantity))) if candidate.available_quantity is not None else 1
            if available_quantity <= 0:
                available_quantity = 1

            delivery_price = Decimal(str(candidate.delivery_price)) if candidate.delivery_price is not None else Decimal("0")
            effective_unit_price = unit_price + (delivery_price / Decimal(str(max(available_quantity, 1))))
            supplier = self.supplier_service.resolve(candidate.seller_name)
            seller_name_normalized = normalize_supplier_name(candidate.seller_name or "")
            supplier_status = supplier.status if supplier is not None else "unknown"

            offer = MarketOffer(
                provider=candidate.provider,
                source=candidate.provider,
                purchase_id=item.purchase_id,
                purchase_item_id=item.id,
                purchase_external_id=item.purchase.external_id if item.purchase else None,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title=candidate.title,
                offer_url=candidate.url,
                seller_name=candidate.seller_name,
                supplier_name=candidate.seller_name or "unknown",
                region=candidate.region,
                region_code=_region_code_from_text(candidate.region),
                unit_price=unit_price,
                available_quantity=available_quantity,
                delivery_price=delivery_price,
                delivery_days=candidate.delivery_days,
                effective_unit_price=effective_unit_price,
                relevance_score=Decimal(str(candidate.relevance_score)),
                is_relevant=False if force_irrelevant else bool(candidate.is_relevant),
                risk_flags=sorted(set(candidate.risk_flags + (["duplicate"] if force_irrelevant else []))),
                comment=candidate.comment,
                raw_payload=_json_safe(candidate.raw_payload),
                match_score=Decimal(str(candidate.match_score)) if candidate.match_score is not None else None,
                match_reasons_json=candidate.match_reasons,
                match_risk_flags_json=candidate.match_risk_flags,
                matched_fields_json=candidate.matched_fields,
                mismatched_fields_json=candidate.mismatched_fields,
                hard_reject_reason=candidate.hard_reject_reason,
                delivery_type=candidate.delivery_type or "unknown",
                delivery_price_type=candidate.delivery_price_type or "unknown",
                pickup_available=candidate.pickup_available,
                delivery_unknown=bool(candidate.delivery_unknown or candidate.delivery_price is None),
                min_order_quantity=candidate.min_order_quantity,
                package_quantity=candidate.package_quantity,
                seller_name_normalized=seller_name_normalized or None,
                supplier_status=supplier_status,
                supplier_id=supplier.id if supplier is not None else None,
                collected_at=utc_now(),
            )
            self.session.add(offer)
            created += 1

        return created

    def _process_manual_mode_item(self, item: PurchaseItem) -> str:
        offers = self.session.scalars(select(MarketOffer).where(MarketOffer.purchase_item_id == item.id)).all()
        if not offers:
            self._mark_needs_manual(item, reason="manual_mode_no_offers")
            return "needs_manual_price_search"

        for offer in offers:
            candidate = MarketOfferCandidate(
                provider=offer.provider,
                purchase_item_id=item.id,
                title=offer.offer_title or offer.item_name,
                url=offer.offer_url,
                seller_name=offer.seller_name,
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
            supplier = self.supplier_service.resolve(offer.seller_name or offer.supplier_name)
            supplier_status = supplier.status if supplier is not None else "unknown"
            relevance = calculate_offer_relevance(
                item,
                candidate,
                supplier_status=supplier_status,
                min_threshold=self.min_match_score,
            )
            offer.is_relevant = relevance.is_relevant if offer.is_relevant else False
            offer.relevance_score = Decimal(str(relevance.score))
            offer.risk_flags = sorted(set((offer.risk_flags or []) + relevance.risk_flags))
            offer.match_score = Decimal(str(relevance.score))
            offer.match_reasons_json = relevance.reasons
            offer.match_risk_flags_json = relevance.risk_flags
            offer.matched_fields_json = relevance.matched_fields
            offer.mismatched_fields_json = relevance.mismatched_fields
            offer.hard_reject_reason = relevance.hard_reject_reason
            if relevance.hard_reject_reason:
                offer.is_relevant = False
            if supplier is not None:
                offer.supplier_id = supplier.id
                offer.supplier_status = supplier.status
            else:
                offer.supplier_status = "unknown"
            offer.seller_name_normalized = normalize_supplier_name(offer.seller_name or offer.supplier_name or "")

        return "ok"

    def _mark_needs_manual(self, item: PurchaseItem, reason: str) -> None:
        calc = self.session.scalar(
            select(ItemCostCalculation).where(
                ItemCostCalculation.purchase_id == item.purchase_id,
                ItemCostCalculation.purchase_item_id == item.id,
            )
        )
        if calc is None:
            calc = ItemCostCalculation(
                purchase_id=item.purchase_id,
                purchase_item_id=item.id,
                status="needs_manual_price_search",
                required_quantity=int(Decimal(str(item.quantity))),
                covered_quantity=0,
                estimated_item_cost=None,
                unknown_delivery_used=False,
                selected_offers=[],
                risk_flags=["needs_manual_price_search"],
                calculation_details_json={"reason": reason},
            )
            self.session.add(calc)
        else:
            calc.status = "needs_manual_price_search"
            calc.risk_flags = sorted(set((calc.risk_flags or []) + ["needs_manual_price_search"]))
            calc.calculation_details_json = {"reason": reason}

    @staticmethod
    def _merge_int_counters(target: dict[str, int], payload: dict[str, Any]) -> None:
        for key, value in payload.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                target[key] = int(target.get(key, 0)) + value

    @staticmethod
    def _derive_needs_manual_reason(diagnostics: dict[str, Any]) -> str:
        stage_counters = diagnostics.get("stage_counters") if isinstance(diagnostics, dict) else None
        if not isinstance(stage_counters, dict):
            return "extraction_failed"

        if int(stage_counters.get("blocked_or_captcha") or 0) > 0:
            return "blocked_page"
        if int(stage_counters.get("no_price_signal") or 0) > 0:
            return "no_price_found"
        if int(stage_counters.get("no_relevant_rows") or 0) > 0 or int(stage_counters.get("non_serp_rescue_no_relevance") or 0) > 0:
            return "low_relevance"
        if (
            int(stage_counters.get("fallback_empty") or 0) > 0
            or int(stage_counters.get("non_serp_rescue_empty") or 0) > 0
            or int(stage_counters.get("non_serp_rescue_exhausted") or 0) > 0
        ):
            return "rescue_exhausted"
        if int(stage_counters.get("invalid_or_junk_url") or 0) > 0 or int(stage_counters.get("non_serp_rescue_failed") or 0) > 0:
            return "extraction_failed"
        return "empty"



def clear_offers_for_mode(session: Session, mode: str, purchase_id: int | None = None, item_id: int | None = None) -> int:
    stmt = delete(MarketOffer).where(MarketOffer.source == mode)
    if purchase_id is not None:
        stmt = stmt.where(MarketOffer.purchase_id == purchase_id)
    if item_id is not None:
        stmt = stmt.where(MarketOffer.purchase_item_id == item_id)

    result = session.execute(stmt)
    session.commit()
    return int(result.rowcount or 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


def _region_code_from_text(region: str | None) -> str | None:
    if not region:
        return None
    lowered = region.lower()
    if "моск" in lowered and "обл" in lowered:
        return "50"
    if "моск" in lowered:
        return "77"
    return None
