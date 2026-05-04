from __future__ import annotations


def decision_from_score(
    *,
    score_total: float,
    risk_level: str,
    has_deadline_expired: bool,
    has_missing_prices: bool,
    blocked_supplier_used: bool,
) -> tuple[str, str]:
    if has_deadline_expired:
        return "reject", "Дедлайн уже истек."
    if blocked_supplier_used:
        return "reject", "Используется заблокированный поставщик."
    if has_missing_prices:
        return "needs_manual_review", "Есть позиции без цены или с неполным покрытием."
    if risk_level == "critical":
        return "reject", "Критический уровень риска."
    if score_total >= 70:
        return "strong_recommend", "Высокий итоговый score и приемлемый риск."
    if score_total >= 45:
        return "recommend", "Достаточный score для участия."
    if score_total >= 20:
        return "watch", "Потенциал есть, но требуется наблюдение/уточнения."
    if risk_level in {"high", "critical"}:
        return "reject", "Низкий score и высокий риск."
    return "ignore", "Низкий score без приоритетов по стратегии."


def next_action_for_decision(
    decision: str,
    *,
    deadline_status: str,
    has_unknown_delivery: bool,
    has_unknown_supplier: bool,
    has_manual_review_items: bool,
) -> str:
    if deadline_status == "deadline_soon":
        return "Проверить дедлайн и срочно подтвердить условия перед подачей."
    if decision == "strong_recommend":
        if has_unknown_delivery:
            return "Проверить доставку по спорным позициям и подать предложение."
        return "Подготовить подачу предложения и финально подтвердить цены."
    if decision == "recommend":
        if has_unknown_supplier:
            return "Проверить поставщика и подтвердить коммерческие условия."
        return "Проверить оставшиеся риски и перейти к подготовке заявки."
    if decision == "needs_manual_review":
        if has_manual_review_items:
            return "Добавить/уточнить цены по позициям, требующим ручной проверки."
        return "Провести ручную валидацию рисков перед решением."
    if decision == "watch":
        return "Оставить в наблюдении и обновить данные ближе к дедлайну."
    if decision == "reject":
        return "Не участвовать при текущих условиях."
    return "Игнорировать закупку, если приоритеты не изменятся."
