from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MarketOffer, Purchase, PurchaseCalculation
from app.utils.logging import get_file_logger


financial_logger = get_file_logger("validation.financial", "financial-check.log")
RISK_LEVELS = ["low", "medium", "high", "critical"]


def escalate_risk_level(current: str | None, severity: str) -> str:
    base = (current or "medium").lower()
    if base not in RISK_LEVELS:
        base = "medium"

    bump = 0
    if severity == "warning":
        bump = 1
    elif severity == "error":
        bump = 2

    idx = min(RISK_LEVELS.index(base) + bump, len(RISK_LEVELS) - 1)
    return RISK_LEVELS[idx]


@dataclass
class FinancialCheckPurchaseResult:
    purchase_id: int
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FinancialCheckSummary:
    checked_purchases: int = 0
    ok_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    rows: list[FinancialCheckPurchaseResult] = field(default_factory=list)


class FinancialCheckService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def check(self, purchase_id: int | None = None) -> FinancialCheckSummary:
        stmt = select(PurchaseCalculation).join(Purchase, Purchase.id == PurchaseCalculation.purchase_id)
        if purchase_id is not None:
            stmt = stmt.where(PurchaseCalculation.purchase_id == purchase_id)

        rows = self.session.scalars(stmt).all()
        summary = FinancialCheckSummary(checked_purchases=len(rows))

        for calc in rows:
            result = self._check_purchase(calc.purchase_id)
            summary.rows.append(result)
            if result.status == "error":
                summary.error_count += 1
            elif result.status == "warning":
                summary.warning_count += 1
            else:
                summary.ok_count += 1

        self.session.commit()
        return summary

    def _check_purchase(self, purchase_id: int) -> FinancialCheckPurchaseResult:
        purchase = self.session.scalar(select(Purchase).where(Purchase.id == purchase_id))
        calc = self.session.scalar(select(PurchaseCalculation).where(PurchaseCalculation.purchase_id == purchase_id))
        if purchase is None or calc is None:
            return FinancialCheckPurchaseResult(
                purchase_id=purchase_id,
                status="error",
                errors=["missing purchase calculation"],
            )

        errors: list[str] = []
        warnings: list[str] = []

        total_cost = Decimal(str(calc.estimated_cost or 0))
        profit = Decimal(str(calc.profit_after_tax or 0))
        margin = Decimal(str(calc.margin_after_tax_percent or 0))
        max_total = Decimal(str(purchase.max_total_price or 0))

        if total_cost <= 0:
            errors.append("total_cost <= 0")
        if max_total > 0 and profit > max_total:
            warnings.append("profit > max_total_price")
        if margin > 100:
            warnings.append("margin > 100%")
        if margin < -50:
            warnings.append("margin < -50%")

        offers_count = self.session.scalar(
            select(func.count(MarketOffer.id)).where(MarketOffer.purchase_id == purchase_id)
        ) or 0
        if offers_count == 0:
            warnings.append("missing offers")

        if errors:
            status = "error"
        elif warnings:
            status = "warning"
        else:
            status = "ok"

        calc.financial_check_status = status
        calc.financial_check_flags_json = sorted(errors + warnings)
        if status in {"warning", "error"}:
            calc.risk_level = escalate_risk_level(calc.risk_level, status)

        if errors or warnings:
            financial_logger.warning(
                "financial check | purchase_id=%s status=%s errors=%s warnings=%s",
                purchase_id,
                status,
                "; ".join(errors) if errors else "-",
                "; ".join(warnings) if warnings else "-",
            )

        return FinancialCheckPurchaseResult(
            purchase_id=purchase_id,
            status=status,
            errors=errors,
            warnings=warnings,
        )
