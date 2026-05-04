from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    CalculationOfferUsage,
    ItemCostCalculation,
    MarketOffer,
    ParticipationStrategy,
    Purchase,
    PurchaseCalculation,
    PurchaseDecisionScore,
    PurchaseWatchlist,
)
from app.services.financial_check_service import FinancialCheckService, escalate_risk_level
from app.scoring.recommendations import decision_from_score, next_action_for_decision
from app.scoring.scoring_v2 import calculate_purchase_score
from app.scoring.strategy import get_active_strategy
from app.services.notification_service import notify_decision_event


RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class DecisionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def evaluate_purchase(self, purchase_id: int) -> PurchaseDecisionScore:
        purchase = self.session.scalar(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(
                selectinload(Purchase.calculation),
                selectinload(Purchase.item_calculations),
            )
        )
        if purchase is None or purchase.calculation is None:
            raise ValueError(f"Purchase {purchase_id} has no calculation")

        calc = purchase.calculation
        financial_result = FinancialCheckService(self.session)._check_purchase(purchase.id)
        strategy = get_active_strategy(self.session)
        offers = self.session.scalars(select(MarketOffer).where(MarketOffer.purchase_id == purchase.id)).all()
        item_calcs = list(purchase.item_calculations or [])
        used_offer_ids = {
            usage.market_offer_id
            for usage in self.session.scalars(
                select(CalculationOfferUsage).join(
                    ItemCostCalculation,
                    ItemCostCalculation.id == CalculationOfferUsage.item_cost_calculation_id,
                ).where(ItemCostCalculation.purchase_id == purchase.id)
            ).all()
            if usage.market_offer_id is not None
        }
        used_offers = [offer for offer in offers if offer.id in used_offer_ids]

        no_price_count = sum(1 for item in item_calcs if item.status in {"no_relevant_offers", "needs_manual_price_search"})
        insufficient_count = sum(1 for item in item_calcs if item.status == "insufficient_market_quantity")
        manual_review_count = sum(1 for item in item_calcs if item.status in {"needs_manual_review", "delivery_unknown", "quantity_unknown"})
        all_positions_ok = len(item_calcs) > 0 and all(item.status == "ok" for item in item_calcs)

        supplier_statuses = [offer.supplier_status or "unknown" for offer in used_offers]
        all_trusted = bool(supplier_statuses) and all(status == "trusted" for status in supplier_statuses)
        risky_supplier_count = sum(1 for status in supplier_statuses if status == "risky")
        unknown_supplier_count = sum(1 for status in supplier_statuses if status == "unknown")
        blocked_supplier_present = any((offer.supplier_status or "unknown") == "blocked" for offer in offers)

        unknown_delivery_count = sum(1 for offer in used_offers if offer.delivery_unknown)
        manual_force_include_count = sum(1 for offer in used_offers if "manual_force_include" in (offer.risk_flags or []))
        low_relevance_used_count = sum(1 for offer in used_offers if "low_relevance" in (offer.risk_flags or []))
        overbuy_required_count = sum(
            1
            for item in item_calcs
            if (item.calculation_details_json or {}).get("overbuy_quantity", 0) not in (None, 0, "0")
        )
        captcha_blocked_count = sum(1 for offer in offers if "captcha_or_blocked" in (offer.risk_flags or []))
        needs_manual_tax_review = "needs_manual_tax_review" in (calc.risk_level or "")

        breakdown = calculate_purchase_score(
            purchase=purchase,
            calc=calc,
            offers=offers,
            all_positions_ok=all_positions_ok,
            manual_review_count=manual_review_count,
            no_price_count=no_price_count,
            insufficient_count=insufficient_count,
            all_trusted_suppliers=all_trusted,
            risky_supplier_count=risky_supplier_count,
            unknown_supplier_count=unknown_supplier_count,
            blocked_supplier_used=blocked_supplier_present,
            unknown_delivery_count=unknown_delivery_count,
            manual_force_include_count=manual_force_include_count,
            low_relevance_used_count=low_relevance_used_count,
            overbuy_required_count=overbuy_required_count,
            captcha_blocked_count=captcha_blocked_count,
            needs_manual_tax_review=needs_manual_tax_review,
        )

        decision, reason = decision_from_score(
            score_total=breakdown.score_total,
            risk_level=breakdown.risk_assessment.risk_level,
            has_deadline_expired=breakdown.deadline_status == "expired",
            has_missing_prices=no_price_count > 0,
            blocked_supplier_used=blocked_supplier_present,
        )
        decision, reason = self._apply_guardrails(
            purchase=purchase,
            calc=calc,
            decision=decision,
            reason=reason,
            offers=offers,
            no_price_count=no_price_count,
            financial_status=financial_result.status,
        )
        decision, reason = self._apply_strategy_overrides(
            strategy=strategy,
            purchase=purchase,
            calc=calc,
            decision=decision,
            reason=reason,
            risk_level=breakdown.risk_assessment.risk_level,
            unknown_delivery_count=unknown_delivery_count,
            unknown_supplier_count=unknown_supplier_count,
            manual_review_count=manual_review_count,
        )
        next_action = next_action_for_decision(
            decision,
            deadline_status=breakdown.deadline_status,
            has_unknown_delivery=unknown_delivery_count > 0,
            has_unknown_supplier=unknown_supplier_count > 0,
            has_manual_review_items=manual_review_count > 0,
        )

        row = self.session.scalar(select(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id == purchase.id))
        if row is None:
            row = PurchaseDecisionScore(purchase_id=purchase.id)
            self.session.add(row)

        row.score_total = breakdown.score_total
        row.score_margin = breakdown.score_margin
        row.score_profit = breakdown.score_profit
        row.score_deadline = breakdown.score_deadline
        row.score_data_quality = breakdown.score_data_quality
        row.score_supplier_quality = breakdown.score_supplier_quality
        row.score_competition = breakdown.score_competition
        row.score_cash_efficiency = breakdown.score_cash_efficiency
        row.score_risk = breakdown.score_risk
        row.risk_level = self._combined_risk_level(
            base=breakdown.risk_assessment.risk_level,
            financial_status=financial_result.status,
        )
        row.decision = decision
        row.decision_status = "needs_review" if self.settings.real_run_mode else "draft"
        row.decision_reason = reason
        row.next_action = next_action
        row.cash_roi_percent = breakdown.cash_roi_percent
        row.deadline_status = breakdown.deadline_status
        row.competition_level = breakdown.competition_level
        row.competition_reason = breakdown.competition_reason
        row.explanation_json = self._build_explanation(
            purchase=purchase,
            calc=calc,
            competition_reason=breakdown.competition_reason,
            risk_level=row.risk_level,
            final_reason=reason,
            financial_result=financial_result,
            decision=decision,
        )
        calc.explanation_summary = row.explanation_json.get("final_reason", reason)

        purchase.deadline_status = breakdown.deadline_status
        self.session.commit()
        self.session.refresh(row)

        notify_decision_event(
            session=self.session,
            purchase_id=purchase.id,
            decision=row.decision,
            score_total=float(row.score_total),
            message=f"Закупка {purchase.external_id}: {row.decision} (score={row.score_total})",
        )
        return row

    def evaluate_all(self) -> int:
        purchases = self.session.scalars(select(Purchase.id).join(PurchaseCalculation, PurchaseCalculation.purchase_id == Purchase.id)).all()
        count = 0
        for purchase_id in purchases:
            self.evaluate_purchase(purchase_id)
            count += 1
        return count

    def get_top_opportunities(self, limit: int = 20) -> list[PurchaseDecisionScore]:
        ignored_ids = set(
            self.session.scalars(
                select(PurchaseWatchlist.purchase_id).where(PurchaseWatchlist.status.in_(["ignored"]))
            ).all()
        )
        rows = self.session.scalars(
            select(PurchaseDecisionScore)
            .where(PurchaseDecisionScore.decision.in_(["strong_recommend", "recommend", "watch"]))
            .order_by(PurchaseDecisionScore.score_total.desc())
            .limit(limit * 3)
        ).all()
        filtered = [row for row in rows if row.purchase_id not in ignored_ids]
        return filtered[:limit]

    def get_needs_review(self, limit: int = 20) -> list[PurchaseDecisionScore]:
        return self.session.scalars(
            select(PurchaseDecisionScore)
            .where(PurchaseDecisionScore.decision == "needs_manual_review")
            .order_by(PurchaseDecisionScore.updated_at.desc())
            .limit(limit)
        ).all()

    def get_rejected(self, limit: int = 20) -> list[PurchaseDecisionScore]:
        return self.session.scalars(
            select(PurchaseDecisionScore)
            .where(PurchaseDecisionScore.decision.in_(["reject", "ignore"]))
            .order_by(PurchaseDecisionScore.updated_at.desc())
            .limit(limit)
        ).all()

    def _apply_strategy_overrides(
        self,
        *,
        strategy: ParticipationStrategy | None,
        purchase: Purchase,
        calc: PurchaseCalculation,
        decision: str,
        reason: str,
        risk_level: str,
        unknown_delivery_count: int,
        unknown_supplier_count: int,
        manual_review_count: int,
    ) -> tuple[str, str]:
        if strategy is None:
            return decision, reason

        if float(calc.margin_after_tax_percent) < float(strategy.min_margin_percent):
            return "reject", "Маржа ниже порога активной стратегии."
        if float(calc.profit_after_tax) < float(strategy.min_profit_amount):
            return "reject", "Прибыль ниже порога активной стратегии."
        if strategy.max_cash_required is not None and float(calc.cash_required) > float(strategy.max_cash_required):
            return "reject", "Требуемый cash выше лимита стратегии."
        if RISK_ORDER.get(risk_level, 4) > RISK_ORDER.get(strategy.max_risk_level, 2):
            return "needs_manual_review", "Риск выше допустимого для стратегии."
        if not strategy.allow_unknown_delivery and unknown_delivery_count > 0:
            return "needs_manual_review", "Стратегия не допускает неизвестную доставку."
        if not strategy.allow_unknown_supplier and unknown_supplier_count > 0:
            return "needs_manual_review", "Стратегия не допускает неизвестных поставщиков."
        if not strategy.allow_manual_review_items and manual_review_count > 0:
            return "needs_manual_review", "Стратегия не допускает позиции с ручной проверкой."
        return decision, reason

    def _apply_guardrails(
        self,
        *,
        purchase: Purchase,
        calc: PurchaseCalculation,
        decision: str,
        reason: str,
        offers: list[MarketOffer],
        no_price_count: int,
        financial_status: str,
    ) -> tuple[str, str]:
        is_strong = decision in {"strong_recommend", "strong_buy"}
        if not is_strong:
            return decision, reason

        guardrails: list[str] = []
        if (purchase.data_quality or "medium") == "low":
            guardrails.append("низкое качество данных")
        if no_price_count > 0 or not offers:
            guardrails.append("нет достаточных ценовых предложений")
        if financial_status == "error":
            guardrails.append("финансовая проверка завершилась ошибкой")
        if float(calc.margin_after_tax_percent or 0) < 20:
            guardrails.append("маржа после налогов ниже 20%")

        if not guardrails:
            return decision, reason
        return "needs_manual_review", "Guardrails: " + "; ".join(guardrails) + "."

    def _combined_risk_level(self, *, base: str, financial_status: str) -> str:
        if financial_status in {"warning", "error"}:
            return escalate_risk_level(base, financial_status)
        return base

    def _build_explanation(
        self,
        *,
        purchase: Purchase,
        calc: PurchaseCalculation,
        competition_reason: str,
        risk_level: str,
        final_reason: str,
        financial_result,
        decision: str,
    ) -> dict:
        margin_value = float(calc.margin_after_tax_percent or 0)
        if margin_value >= 25:
            profit_note = f"Высокая маржа ({margin_value:.1f}%)."
        elif margin_value >= 10:
            profit_note = f"Умеренная маржа ({margin_value:.1f}%)."
        else:
            profit_note = f"Низкая маржа ({margin_value:.1f}%)."

        quality = purchase.data_quality or "medium"
        financial_note = "Финансовых аномалий не выявлено."
        if financial_result.status == "warning":
            financial_note = "Есть финансовые предупреждения: " + ", ".join(financial_result.warnings[:3])
        elif financial_result.status == "error":
            financial_note = "Есть критичные финансовые ошибки: " + ", ".join(financial_result.errors[:3])

        return {
            "profit": profit_note,
            "competition": competition_reason,
            "data_quality": quality,
            "risk": f"risk_level={risk_level}; {financial_note}",
            "final_reason": final_reason,
            "decision": decision,
        }
