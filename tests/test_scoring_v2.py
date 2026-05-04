from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now
from decimal import Decimal

from app.models import Purchase, PurchaseCalculation
from app.scoring.scoring_v2 import calculate_purchase_score


def _base_purchase(deadline_hours: int = 48) -> Purchase:
    return Purchase(
        source="fixture",
        external_id="S-1",
        title="Поставка бумаги",
        submission_deadline=utc_now() + timedelta(hours=deadline_hours),
        max_total_price=Decimal("200000"),
    )


def _base_calc(margin_after_tax: str = "30", profit_after_tax: str = "60000", cash_required: str = "100000") -> PurchaseCalculation:
    return PurchaseCalculation(
        purchase_id=1,
        max_total_price=Decimal("200000"),
        estimated_cost=Decimal("120000"),
        estimated_profit=Decimal(profit_after_tax),
        margin_percent=Decimal(margin_after_tax),
        cash_required=Decimal(cash_required),
        recommendation_status="ok",
        problematic_items_count=0,
        unknown_delivery_items_count=0,
        attractiveness_score=Decimal("50"),
        vat_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        cost_before_tax=Decimal("120000"),
        cost_after_tax=Decimal("120000"),
        profit_before_tax=Decimal(profit_after_tax),
        profit_after_tax=Decimal(profit_after_tax),
        margin_before_tax_percent=Decimal(margin_after_tax),
        margin_after_tax_percent=Decimal(margin_after_tax),
    )


def test_high_margin_gives_high_score_margin() -> None:
    result = calculate_purchase_score(
        purchase=_base_purchase(),
        calc=_base_calc(margin_after_tax="36", profit_after_tax="120000"),
        offers=[],
        all_positions_ok=True,
        manual_review_count=0,
        no_price_count=0,
        insufficient_count=0,
        all_trusted_suppliers=True,
        risky_supplier_count=0,
        unknown_supplier_count=0,
        blocked_supplier_used=False,
        unknown_delivery_count=0,
        manual_force_include_count=0,
        low_relevance_used_count=0,
        overbuy_required_count=0,
        captcha_blocked_count=0,
        needs_manual_tax_review=False,
    )
    assert result.score_margin == 30


def test_low_margin_gives_negative_score_margin() -> None:
    result = calculate_purchase_score(
        purchase=_base_purchase(),
        calc=_base_calc(margin_after_tax="8", profit_after_tax="2000"),
        offers=[],
        all_positions_ok=True,
        manual_review_count=0,
        no_price_count=0,
        insufficient_count=0,
        all_trusted_suppliers=True,
        risky_supplier_count=0,
        unknown_supplier_count=0,
        blocked_supplier_used=False,
        unknown_delivery_count=0,
        manual_force_include_count=0,
        low_relevance_used_count=0,
        overbuy_required_count=0,
        captcha_blocked_count=0,
        needs_manual_tax_review=False,
    )
    assert result.score_margin == -30


def test_deadline_less_than_3_hours_penalized() -> None:
    result = calculate_purchase_score(
        purchase=_base_purchase(deadline_hours=2),
        calc=_base_calc(),
        offers=[],
        all_positions_ok=True,
        manual_review_count=0,
        no_price_count=0,
        insufficient_count=0,
        all_trusted_suppliers=True,
        risky_supplier_count=0,
        unknown_supplier_count=0,
        blocked_supplier_used=False,
        unknown_delivery_count=0,
        manual_force_include_count=0,
        low_relevance_used_count=0,
        overbuy_required_count=0,
        captcha_blocked_count=0,
        needs_manual_tax_review=False,
    )
    assert result.score_deadline == -30
    assert result.deadline_status == "deadline_soon"


def test_all_positions_ok_gives_data_quality_bonus() -> None:
    result = calculate_purchase_score(
        purchase=_base_purchase(),
        calc=_base_calc(),
        offers=[],
        all_positions_ok=True,
        manual_review_count=0,
        no_price_count=0,
        insufficient_count=0,
        all_trusted_suppliers=True,
        risky_supplier_count=0,
        unknown_supplier_count=0,
        blocked_supplier_used=False,
        unknown_delivery_count=0,
        manual_force_include_count=0,
        low_relevance_used_count=0,
        overbuy_required_count=0,
        captcha_blocked_count=0,
        needs_manual_tax_review=False,
    )
    assert result.score_data_quality == 20
