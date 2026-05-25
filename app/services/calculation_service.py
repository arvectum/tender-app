from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import CalculationOfferUsage, ItemCostCalculation, MarketOffer, Purchase, PurchaseCalculation
from app.services.business_rules_service import BusinessRulesService
from app.services.explanation_service import build_purchase_explanation
from app.services.notification_service import notify_recommended_purchase
from app.services.ranking_service import calculate_attractiveness_score


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_required_quantity(quantity_value: Decimal | int | float | None) -> int:
    if quantity_value is None:
        return 0
    quantity_decimal = Decimal(str(quantity_value))
    if quantity_decimal <= 0:
        return 0
    return int(quantity_decimal.to_integral_value(rounding=ROUND_HALF_UP))


def calculate_all_purchases(session: Session) -> int:
    purchases = session.scalars(select(Purchase).options(selectinload(Purchase.items))).all()

    session.execute(delete(CalculationOfferUsage))
    session.execute(delete(ItemCostCalculation))
    session.execute(delete(PurchaseCalculation))
    session.commit()

    for purchase in purchases:
        calculate_purchase(session, purchase.id)

    return len(purchases)


def calculate_purchase(session: Session, purchase_id: int) -> PurchaseCalculation:
    settings = get_settings()
    rules = BusinessRulesService(session)
    purchase = session.scalar(
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(selectinload(Purchase.items), selectinload(Purchase.calculation))
    )
    if purchase is None:
        raise ValueError(f"Purchase id={purchase_id} not found")

    delivery_mode = rules.get_typed("DELIVERY_MODE", settings.delivery_mode, str)
    default_unknown_delivery_cost = Decimal(
        str(rules.get_typed("DEFAULT_UNKNOWN_DELIVERY_COST", settings.default_unknown_delivery_cost, float))
    )
    pickup_allowed = rules.get_typed("PICKUP_ALLOWED", settings.pickup_allowed, lambda v: str(v).lower() in {"1", "true", "yes", "on"})
    min_margin_percent = rules.get_typed("MIN_MARGIN_PERCENT", settings.min_margin_percent, float)
    vat_mode = rules.get_typed("VAT_MODE", settings.vat_mode, str)
    vat_rate = Decimal(str(rules.get_typed("VAT_RATE", settings.vat_rate, float)))
    tax_mode = rules.get_typed("TAX_MODE", settings.tax_mode, str)

    estimated_cost = Decimal("0")
    problematic_items_count = 0
    unknown_delivery_items_count = 0
    tax_risk = False

    for item in purchase.items:
        item_result = _calculate_item_cost(
            session=session,
            purchase=purchase,
            item_id=item.id,
            required_quantity=_to_required_quantity(item.quantity),
            default_unknown_delivery_cost=default_unknown_delivery_cost,
            delivery_mode=delivery_mode,
            pickup_allowed=pickup_allowed,
        )

        estimated_cost += item_result["estimated_cost"]
        status = item_result["status"]

        if status != "ok":
            problematic_items_count += 1
        if "delivery_unknown" in item_result["risk_flags"]:
            unknown_delivery_items_count += 1

    max_total_price = Decimal(purchase.max_total_price or Decimal("0"))
    if max_total_price <= 0:
        items_max_total = sum((Decimal(item.max_total_price or Decimal("0")) for item in purchase.items), Decimal("0"))
        if items_max_total > 0:
            max_total_price = items_max_total
    # Fail-closed: if there are problematic/unpriced items, do not publish optimistic
    # margins from zero/partial costs. Clamp estimate to purchase budget floor.
    if problematic_items_count > 0 and estimated_cost < max_total_price:
        estimated_cost = max_total_price

    cost_before_tax = _quantize_money(estimated_cost)
    vat_amount = _calculate_vat(cost_before_tax, vat_mode=vat_mode, vat_rate=vat_rate)
    cost_after_tax = _quantize_money(cost_before_tax + vat_amount)

    profit_before_tax = _quantize_money(max_total_price - cost_before_tax)
    tax_amount, needs_manual_tax_review = _calculate_tax(
        max_total_price=max_total_price,
        profit_before_tax=profit_before_tax,
        tax_mode=tax_mode,
    )
    tax_risk = needs_manual_tax_review
    profit_after_tax = _quantize_money(max_total_price - cost_after_tax - tax_amount)

    margin_before_tax = _percent(profit_before_tax, max_total_price)
    margin_after_tax = _percent(profit_after_tax, max_total_price)

    recommendation_status = pick_recommendation_status(
        margin_percent=float(margin_after_tax),
        min_margin_percent=min_margin_percent,
        problematic_items_count=problematic_items_count,
    )
    if tax_risk and recommendation_status == "ok":
        recommendation_status = "needs_review"

    attractiveness_score = Decimal(
        str(
            calculate_attractiveness_score(
                margin_percent=float(margin_after_tax),
                estimated_profit=float(profit_after_tax),
                problematic_items_count=problematic_items_count,
                unknown_delivery_items_count=unknown_delivery_items_count,
                submission_deadline=purchase.submission_deadline,
            )
        )
    )

    result = PurchaseCalculation(
        purchase_id=purchase.id,
        max_total_price=_quantize_money(max_total_price),
        estimated_cost=cost_before_tax,
        estimated_profit=profit_after_tax,
        margin_percent=margin_after_tax,
        cash_required=cost_after_tax,
        recommendation_status=recommendation_status,
        problematic_items_count=problematic_items_count,
        unknown_delivery_items_count=unknown_delivery_items_count,
        attractiveness_score=attractiveness_score,
        vat_amount=vat_amount,
        tax_amount=tax_amount,
        cost_before_tax=cost_before_tax,
        cost_after_tax=cost_after_tax,
        profit_before_tax=profit_before_tax,
        profit_after_tax=profit_after_tax,
        margin_before_tax_percent=margin_before_tax,
        margin_after_tax_percent=margin_after_tax,
        risk_level=_risk_level(recommendation_status, problematic_items_count, unknown_delivery_items_count, tax_risk),
        verification_status="unverified" if settings.real_run_mode else "verified",
        financial_check_status="unknown",
        financial_check_flags_json=[],
    )
    session.add(result)
    session.commit()
    session.refresh(result)

    explanation = build_purchase_explanation(session, purchase.id)
    result.explanation_summary = explanation.summary
    session.commit()
    session.refresh(result)

    if result.recommendation_status == "ok":
        notify_recommended_purchase(
            session=session,
            purchase_id=purchase.id,
            margin_percent=float(result.margin_after_tax_percent),
            estimated_profit=float(result.profit_after_tax),
            message=(
                f"Recommended purchase #{purchase.id} ({purchase.external_id})\n"
                f"Margin after tax: {result.margin_after_tax_percent}%\n"
                f"Profit after tax: {result.profit_after_tax}"
            ),
        )

    return result


def _calculate_item_cost(
    session: Session,
    purchase: Purchase,
    item_id: int,
    required_quantity: int,
    default_unknown_delivery_cost: Decimal,
    delivery_mode: str,
    pickup_allowed: bool,
) -> dict:
    offers = session.scalars(select(MarketOffer).where(MarketOffer.purchase_item_id == item_id)).all()

    if not offers:
        item_name = next(item.item_name for item in purchase.items if item.id == item_id)
        offers = session.scalars(
            select(MarketOffer).where(
                MarketOffer.purchase_item_id.is_(None),
                MarketOffer.item_name.ilike(item_name),
            )
        ).all()

    excluded_reasons: list[dict] = []
    relevant_candidates: list[MarketOffer] = []
    fallback_candidates: list[MarketOffer] = []
    has_manual_blocker = False
    low_relevance_fallback_used = False

    for offer in offers:
        risk_flags = offer.risk_flags or []
        if "captcha_or_blocked" in risk_flags or "needs_manual_price_search" in risk_flags:
            has_manual_blocker = True

        if offer.supplier_status == "blocked":
            excluded_reasons.append({"offer_id": offer.id, "reason": "blocked_supplier"})
            continue

        if offer.manual_override_exclude:
            excluded_reasons.append({"offer_id": offer.id, "reason": "manual_exclude"})
            continue

        if not _effective_offer_relevance(offer):
            excluded_reasons.append({"offer_id": offer.id, "reason": "not_relevant"})
            if (
                not has_manual_blocker
                and not offer.hard_reject_reason
                and Decimal(str(offer.unit_price)) > 0
                and not (delivery_mode == "strict" and _is_delivery_unknown(offer))
            ):
                fallback_candidates.append(offer)
            continue

        if delivery_mode == "strict" and _is_delivery_unknown(offer):
            excluded_reasons.append({"offer_id": offer.id, "reason": "delivery_unknown_strict"})
            continue

        if Decimal(str(offer.unit_price)) <= 0:
            excluded_reasons.append({"offer_id": offer.id, "reason": "non_positive_price"})
            continue

        relevant_candidates.append(offer)

    if not relevant_candidates and fallback_candidates:
        relevant_candidates = fallback_candidates
        low_relevance_fallback_used = True

    if not relevant_candidates:
        status = "needs_manual_price_search" if has_manual_blocker else "no_relevant_offers"
        session.add(
            ItemCostCalculation(
                purchase_id=purchase.id,
                purchase_item_id=item_id,
                status=status,
                required_quantity=required_quantity,
                covered_quantity=0,
                estimated_item_cost=None,
                unknown_delivery_used=False,
                selected_offers=[],
                risk_flags=[status] if status != "no_relevant_offers" else [],
                calculation_details_json={
                    "required_quantity": required_quantity,
                    "used_offers": [],
                    "total_cost": None,
                    "excluded_offers": excluded_reasons,
                },
            )
        )
        session.flush()
        return {
            "estimated_cost": Decimal("0"),
            "status": status,
            "risk_flags": [status] if status != "no_relevant_offers" else [],
        }

    relevant_candidates.sort(key=lambda row: (_effective_unit_price(row), Decimal(str(row.unit_price)), row.id))

    remaining = required_quantity
    total_cost = Decimal("0")
    covered_quantity = 0
    unknown_delivery_used = False
    quantity_unknown_used = False
    overbuy_total = 0
    overbuy_cost = Decimal("0")

    selected_offer_rows: list[dict] = []
    usage_payloads: list[dict] = []

    for offer in relevant_candidates:
        if remaining <= 0:
            break

        available = max(int(offer.available_quantity or 0), 0)
        if available <= 0:
            excluded_reasons.append({"offer_id": offer.id, "reason": "zero_available"})
            continue

        min_order_quantity = max(int(offer.min_order_quantity or 0), 0)
        package_quantity = max(int(offer.package_quantity or 0), 0)
        desired_used = min(remaining, available)

        purchased_quantity = desired_used
        if min_order_quantity > purchased_quantity:
            purchased_quantity = min_order_quantity
        if package_quantity > 0:
            purchased_quantity = int(math.ceil(purchased_quantity / package_quantity) * package_quantity)

        if purchased_quantity > available:
            excluded_reasons.append({"offer_id": offer.id, "reason": "min_order_or_package_exceeds_available"})
            continue

        used_quantity = min(desired_used, purchased_quantity)
        overbuy_quantity = max(purchased_quantity - used_quantity, 0)

        unit_price = Decimal(str(offer.unit_price))
        delivery_cost = _delivery_cost_for_offer(
            offer=offer,
            purchased_quantity=purchased_quantity,
            available_quantity=available,
            default_unknown_delivery_cost=default_unknown_delivery_cost,
            delivery_mode=delivery_mode,
            pickup_allowed=pickup_allowed,
        )
        subtotal = unit_price * Decimal(str(purchased_quantity))
        total_for_offer = subtotal + delivery_cost
        total_cost += total_for_offer
        covered_quantity += used_quantity
        remaining -= used_quantity
        overbuy_total += overbuy_quantity
        if overbuy_quantity > 0:
            overbuy_cost += unit_price * Decimal(str(overbuy_quantity))

        risk_flags = offer.risk_flags or []
        if offer.manual_override_include and "manual_force_include" not in risk_flags:
            risk_flags = sorted(set(risk_flags + ["manual_force_include"]))
        if _is_delivery_unknown(offer):
            unknown_delivery_used = True
        if "quantity_unknown" in risk_flags:
            quantity_unknown_used = True
        if overbuy_quantity > 0:
            risk_flags = sorted(set(risk_flags + ["overbuy_required"]))
        if offer.supplier_status == "risky":
            risk_flags = sorted(set(risk_flags + ["risky_supplier"]))

        selected_offer_rows.append(
            {
                "offer_id": offer.id,
                "title": offer.offer_title or offer.item_name,
                "seller_name": offer.seller_name or offer.supplier_name,
                "required_quantity": required_quantity,
                "purchased_quantity": purchased_quantity,
                "used_quantity": used_quantity,
                "overbuy_quantity": overbuy_quantity,
                "overbuy_cost": str(_quantize_money(unit_price * Decimal(str(overbuy_quantity)))),
                "unit_price": str(unit_price),
                "delivery_price": str(_quantize_money(delivery_cost)),
                "total": str(_quantize_money(total_for_offer)),
            }
        )
        usage_payloads.append(
            {
                "offer_id": offer.id,
                "taken_quantity": used_quantity,
                "unit_price": unit_price,
                "delivery_price": _quantize_money(delivery_cost),
                "total_cost": _quantize_money(total_for_offer),
            }
        )

    if covered_quantity < required_quantity:
        status = "insufficient_market_quantity"
    elif unknown_delivery_used:
        status = "delivery_unknown"
    elif quantity_unknown_used:
        status = "quantity_unknown"
    else:
        status = "ok"

    calc_risk_flags = _build_risk_flags(status=status, unknown_delivery_used=unknown_delivery_used, quantity_unknown_used=quantity_unknown_used)
    if low_relevance_fallback_used:
        calc_risk_flags = sorted(set(calc_risk_flags + ["low_relevance_fallback"]))

    calc = ItemCostCalculation(
        purchase_id=purchase.id,
        purchase_item_id=item_id,
        status=status,
        required_quantity=required_quantity,
        covered_quantity=covered_quantity,
        estimated_item_cost=_quantize_money(total_cost),
        unknown_delivery_used=unknown_delivery_used,
        selected_offers=selected_offer_rows,
        risk_flags=calc_risk_flags,
        calculation_details_json={
            "required_quantity": required_quantity,
            "used_offers": selected_offer_rows,
            "total_cost": str(_quantize_money(total_cost)),
            "overbuy_quantity": overbuy_total,
            "overbuy_cost": str(_quantize_money(overbuy_cost)),
            "excluded_offers": excluded_reasons,
            "low_relevance_fallback_used": low_relevance_fallback_used,
        },
    )
    session.add(calc)
    session.flush()

    for usage in usage_payloads:
        session.add(
            CalculationOfferUsage(
                item_cost_calculation_id=calc.id,
                market_offer_id=usage["offer_id"],
                taken_quantity=usage["taken_quantity"],
                unit_price=usage["unit_price"],
                delivery_price_allocated=usage["delivery_price"],
                total_cost=usage["total_cost"],
            )
        )

    return {
        "estimated_cost": _quantize_money(total_cost),
        "status": status,
        "risk_flags": calc_risk_flags,
    }


def _is_delivery_unknown(offer: MarketOffer) -> bool:
    if offer.delivery_unknown:
        return True
    if offer.delivery_price is None:
        return True
    return False


def _delivery_cost_for_offer(
    offer: MarketOffer,
    purchased_quantity: int,
    available_quantity: int,
    default_unknown_delivery_cost: Decimal,
    delivery_mode: str,
    pickup_allowed: bool,
) -> Decimal:
    if (offer.delivery_type or "unknown") == "pickup":
        if pickup_allowed:
            return Decimal("0")
        return default_unknown_delivery_cost

    if (offer.delivery_price_type or "unknown") == "included":
        return Decimal("0")

    raw_delivery = Decimal(str(offer.delivery_price)) if offer.delivery_price is not None else None
    if raw_delivery is None:
        if delivery_mode == "optimistic":
            return Decimal("0")
        return default_unknown_delivery_cost

    if (offer.delivery_price_type or "unknown") == "per_unit":
        return _quantize_money(raw_delivery * Decimal(str(purchased_quantity)))

    # per_order / unknown -> allocate proportionally to taken volume.
    ratio = Decimal(str(purchased_quantity)) / Decimal(str(max(available_quantity, 1)))
    ratio = min(Decimal("1"), max(Decimal("0"), ratio))
    return _quantize_money(raw_delivery * ratio)


def _effective_unit_price(offer: MarketOffer) -> Decimal:
    if offer.effective_unit_price is not None:
        return Decimal(str(offer.effective_unit_price))

    unit = Decimal(str(offer.unit_price))
    qty = max(int(offer.available_quantity or 0), 1)
    delivery = Decimal(str(offer.delivery_price)) if offer.delivery_price is not None else Decimal("0")
    return unit + (delivery / Decimal(str(qty)))


def _build_risk_flags(status: str, unknown_delivery_used: bool, quantity_unknown_used: bool) -> list[str]:
    flags: list[str] = []
    if status in {"needs_manual_price_search", "insufficient_market_quantity", "no_relevant_offers"}:
        flags.append(status)
    if unknown_delivery_used:
        flags.append("delivery_unknown")
    if quantity_unknown_used:
        flags.append("quantity_unknown")
    return sorted(set(flags))


def _effective_offer_relevance(offer: MarketOffer) -> bool:
    if offer.manual_override_exclude:
        return False
    if offer.manual_override_include:
        return True
    if offer.manual_override_relevance is not None:
        return offer.manual_override_relevance
    return offer.is_relevant


def _calculate_vat(cost_before_tax: Decimal, vat_mode: str, vat_rate: Decimal) -> Decimal:
    if vat_mode == "excluded":
        return _quantize_money(cost_before_tax * vat_rate / Decimal("100"))
    return Decimal("0")


def _calculate_tax(max_total_price: Decimal, profit_before_tax: Decimal, tax_mode: str) -> tuple[Decimal, bool]:
    if tax_mode == "ignore":
        return Decimal("0"), False
    if tax_mode == "simplified_income":
        return _quantize_money(max_total_price * Decimal("0.06")), False
    if tax_mode == "simplified_income_expense":
        if profit_before_tax <= 0:
            return Decimal("0"), False
        return _quantize_money(profit_before_tax * Decimal("0.15")), False
    if tax_mode == "general":
        return Decimal("0"), True
    return Decimal("0"), False


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    raw = _quantize_money((numerator / denominator) * Decimal("100"))
    # Fits DB column Numeric(8,2) used by margin_*_percent and margin_percent.
    upper = Decimal("999999.99")
    lower = Decimal("-999999.99")
    if raw > upper:
        return upper
    if raw < lower:
        return lower
    return raw


def _risk_level(recommendation_status: str, problematic_items_count: int, unknown_delivery_items_count: int, tax_risk: bool) -> str:
    if recommendation_status == "not_recommended":
        return "high"
    if tax_risk or problematic_items_count > 0 or unknown_delivery_items_count > 0:
        return "medium"
    return "low"


def pick_recommendation_status(margin_percent: float, min_margin_percent: float, problematic_items_count: int) -> str:
    if margin_percent < min_margin_percent:
        return "not_recommended"
    if problematic_items_count > 0:
        return "needs_review"
    return "ok"
