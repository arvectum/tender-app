from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ItemCostCalculation, Purchase, PurchaseCalculation


@dataclass
class PurchaseExplanation:
    summary: str
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    recommendation_reason: str = ""
    next_actions: list[str] = field(default_factory=list)


def build_purchase_explanation(session: Session, purchase_id: int) -> PurchaseExplanation:
    purchase = session.scalar(
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(selectinload(Purchase.calculation), selectinload(Purchase.item_calculations))
    )
    if purchase is None or purchase.calculation is None:
        return PurchaseExplanation(
            summary="Расчет отсутствует.",
            recommendation_reason="Не выполнен расчет закупки.",
            next_actions=["Запустить calculate/recalculate."],
        )

    calc: PurchaseCalculation = purchase.calculation
    item_calcs: list[ItemCostCalculation] = list(purchase.item_calculations or [])
    positive: list[str] = []
    negative: list[str] = []
    risk: list[str] = []
    next_actions: list[str] = []

    if all(item.status == "ok" for item in item_calcs) and item_calcs:
        positive.append(f"Все позиции имеют релевантные предложения ({len(item_calcs)} шт).")
    else:
        problem_count = sum(1 for item in item_calcs if item.status != "ok")
        negative.append(f"Есть проблемные позиции: {problem_count}.")
        next_actions.append("Проверить позиции со статусами no_relevant_offers/insufficient_market_quantity.")

    if float(calc.margin_after_tax_percent) >= 20:
        positive.append("Маржа после налогов выше 20%.")
    else:
        negative.append("Маржа после налогов ниже целевого порога 20%.")

    if calc.unknown_delivery_items_count > 0:
        risk.append(f"Позиции с неизвестной доставкой: {calc.unknown_delivery_items_count}.")
        next_actions.append("Уточнить условия доставки по позициям с delivery_unknown.")

    if calc.recommendation_status == "ok":
        summary = (
            f"Закупка рекомендована: маржа после налогов {calc.margin_after_tax_percent}%, "
            f"расчет закрыт по {len(item_calcs)} позициям."
        )
        reason = "Маржа выше порога и критичных блокеров не обнаружено."
    elif calc.recommendation_status == "not_recommended":
        summary = (
            f"Закупка не рекомендована: маржа после налогов {calc.margin_after_tax_percent}%, "
            "ниже минимального порога."
        )
        reason = "Недостаточная маржинальность после учета налогов/доставки."
    else:
        summary = (
            f"Закупка требует проверки: маржа после налогов {calc.margin_after_tax_percent}%, "
            "но есть рисковые позиции."
        )
        reason = "Есть рисковые факторы, влияющие на надежность расчета."

    if not next_actions:
        next_actions.append("Проверить актуальность цен перед подачей предложения.")

    return PurchaseExplanation(
        summary=summary,
        positive_factors=positive,
        negative_factors=negative,
        risk_factors=risk,
        recommendation_reason=reason,
        next_actions=next_actions,
    )
