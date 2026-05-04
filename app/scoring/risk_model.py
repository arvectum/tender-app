from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskAssessment:
    risk_penalty: float
    risk_level: str
    reasons: list[str] = field(default_factory=list)


def assess_risk(
    *,
    unknown_delivery_count: int,
    manual_force_include_count: int,
    low_relevance_used_count: int,
    overbuy_required_count: int,
    captcha_blocked_count: int,
    needs_manual_tax_review: bool,
    risky_supplier_count: int,
    insufficient_quantity_count: int,
    blocked_supplier_used: bool,
) -> RiskAssessment:
    penalty = 0.0
    reasons: list[str] = []

    penalty += unknown_delivery_count * 5
    penalty += manual_force_include_count * 10
    penalty += low_relevance_used_count * 15
    penalty += overbuy_required_count * 5
    penalty += captcha_blocked_count * 10
    penalty += risky_supplier_count * 20
    penalty += insufficient_quantity_count * 50
    if needs_manual_tax_review:
        penalty += 15
        reasons.append("needs_manual_tax_review")
    if blocked_supplier_used:
        penalty += 100
        reasons.append("blocked_supplier_used")

    if penalty >= 100:
        level = "critical"
    elif penalty >= 60:
        level = "high"
    elif penalty >= 25:
        level = "medium"
    else:
        level = "low"

    return RiskAssessment(risk_penalty=penalty, risk_level=level, reasons=reasons)
