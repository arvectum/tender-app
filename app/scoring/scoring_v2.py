from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models import MarketOffer, Purchase, PurchaseCalculation
from app.scoring.risk_model import RiskAssessment, assess_risk
from app.utils.time import utc_now


@dataclass
class ScoreBreakdown:
    score_total: float
    score_margin: float
    score_profit: float
    score_deadline: float
    score_data_quality: float
    score_supplier_quality: float
    score_competition: float
    score_cash_efficiency: float
    score_risk: float
    cash_roi_percent: float
    deadline_status: str
    risk_assessment: RiskAssessment
    competition_level: str
    competition_reason: str


def _margin_score(margin_after_tax: float) -> float:
    if margin_after_tax >= 35:
        return 30
    if margin_after_tax >= 25:
        return 20
    if margin_after_tax >= 20:
        return 10
    if margin_after_tax >= 10:
        return 0
    return -30


def _profit_score(profit_after_tax: float) -> float:
    if profit_after_tax >= 100000:
        return 30
    if profit_after_tax >= 50000:
        return 20
    if profit_after_tax >= 20000:
        return 10
    if profit_after_tax >= 5000:
        return 5
    return 0


def _deadline_score(deadline: datetime | None) -> tuple[float, str]:
    if deadline is None:
        return -10, "active"
    hours = (deadline - utc_now()).total_seconds() / 3600
    if hours <= 0:
        return -100, "expired"
    if hours < 3:
        return -30, "deadline_soon"
    if hours < 12:
        return -10, "deadline_soon"
    if hours < 24:
        return 3, "deadline_soon"
    return 10, "active"


def _data_quality_score(
    *,
    all_positions_ok: bool,
    manual_review_count: int,
    no_price_count: int,
    insufficient_count: int,
) -> float:
    if no_price_count > 0:
        return -30
    if insufficient_count > 0:
        return -40
    if manual_review_count > 0:
        return -10
    if all_positions_ok:
        return 20
    return 0


def _supplier_quality_score(*, all_trusted: bool, risky_count: int, unknown_count: int, blocked_used: bool) -> float:
    if blocked_used:
        return -100
    if all_trusted:
        return 10
    score = 0.0
    if risky_count > 0:
        score -= 15
    if unknown_count > 0:
        score -= 3
    return score


def _cash_efficiency_score(profit_after_tax: float, cash_required: float) -> tuple[float, float]:
    if cash_required <= 0:
        return 0.0, 0.0
    roi = (profit_after_tax / cash_required) * 100
    if roi >= 50:
        return 20, roi
    if roi >= 30:
        return 10, roi
    if roi >= 15:
        return 5, roi
    return -10, roi


def _competition_stub(purchase: Purchase, offers: list[MarketOffer], margin_after_tax_percent: float, deadline_status: str) -> tuple[float, str, str]:
    offer_count = len(offers)
    text = (purchase.title or "").lower()
    mass_goods = any(word in text for word in ["бумага", "картридж", "канцел"])
    if mass_goods and margin_after_tax_percent >= 30:
        return -10.0, "high", "Высокая маржа у массового товара: ожидается конкуренция."
    if offer_count >= 8:
        return -8.0, "high", "Найдено много рыночных предложений, товар массовый."
    if offer_count <= 2:
        return -2.0, "low", "Найдено мало предложений, нишевая позиция."
    if deadline_status == "deadline_soon":
        return -3.0, "medium", "До дедлайна мало времени, конкуренция может быть ниже, но риск выше."
    return -5.0, "medium", "Средняя рыночная конкуренция."


def calculate_purchase_score(
    *,
    purchase: Purchase,
    calc: PurchaseCalculation,
    offers: list[MarketOffer],
    all_positions_ok: bool,
    manual_review_count: int,
    no_price_count: int,
    insufficient_count: int,
    all_trusted_suppliers: bool,
    risky_supplier_count: int,
    unknown_supplier_count: int,
    blocked_supplier_used: bool,
    unknown_delivery_count: int,
    manual_force_include_count: int,
    low_relevance_used_count: int,
    overbuy_required_count: int,
    captcha_blocked_count: int,
    needs_manual_tax_review: bool,
) -> ScoreBreakdown:
    margin_after_tax = float(calc.margin_after_tax_percent)
    profit_after_tax = float(calc.profit_after_tax)
    cash_required = float(calc.cash_required)

    score_margin = _margin_score(margin_after_tax)
    score_profit = _profit_score(profit_after_tax)
    score_deadline, deadline_status = _deadline_score(purchase.submission_deadline)
    score_data_quality = _data_quality_score(
        all_positions_ok=all_positions_ok,
        manual_review_count=manual_review_count,
        no_price_count=no_price_count,
        insufficient_count=insufficient_count,
    )
    score_supplier_quality = _supplier_quality_score(
        all_trusted=all_trusted_suppliers,
        risky_count=risky_supplier_count,
        unknown_count=unknown_supplier_count,
        blocked_used=blocked_supplier_used,
    )
    score_cash_efficiency, roi = _cash_efficiency_score(profit_after_tax=profit_after_tax, cash_required=cash_required)
    score_competition, competition_level, competition_reason = _competition_stub(
        purchase=purchase,
        offers=offers,
        margin_after_tax_percent=margin_after_tax,
        deadline_status=deadline_status,
    )

    risk = assess_risk(
        unknown_delivery_count=unknown_delivery_count,
        manual_force_include_count=manual_force_include_count,
        low_relevance_used_count=low_relevance_used_count,
        overbuy_required_count=overbuy_required_count,
        captcha_blocked_count=captcha_blocked_count,
        needs_manual_tax_review=needs_manual_tax_review,
        risky_supplier_count=risky_supplier_count,
        insufficient_quantity_count=insufficient_count,
        blocked_supplier_used=blocked_supplier_used,
    )

    score_total = (
        score_margin
        + score_profit
        + score_deadline
        + score_data_quality
        + score_supplier_quality
        + score_cash_efficiency
        + score_competition
        - risk.risk_penalty
    )

    return ScoreBreakdown(
        score_total=round(score_total, 2),
        score_margin=score_margin,
        score_profit=score_profit,
        score_deadline=score_deadline,
        score_data_quality=score_data_quality,
        score_supplier_quality=score_supplier_quality,
        score_competition=abs(score_competition),
        score_cash_efficiency=score_cash_efficiency,
        score_risk=risk.risk_penalty,
        cash_roi_percent=round(roi, 2),
        deadline_status=deadline_status,
        risk_assessment=risk,
        competition_level=competition_level,
        competition_reason=competition_reason,
    )
