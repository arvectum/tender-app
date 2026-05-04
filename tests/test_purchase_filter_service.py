from decimal import Decimal

from app.connectors.base import ParsedPurchase, ParsedPurchaseItem
from app.services.purchase_filter_service import filter_purchase


def _make_purchase(title: str, item_name: str, status: str = "Прием предложений") -> ParsedPurchase:
    return ParsedPurchase(
        source="mos_portal",
        external_id="x-1",
        title=title,
        status=status,
        region="Москва",
        items=[ParsedPurchaseItem(name=item_name, quantity=Decimal("1"))],
    )


def test_service_purchase_is_excluded() -> None:
    purchase = _make_purchase("Оказание услуг по уборке", "Услуга уборки")
    decision = filter_purchase(purchase)
    assert decision.include is False
    assert decision.reason == "service_or_work"


def test_work_purchase_is_excluded() -> None:
    purchase = _make_purchase("Выполнение работ по ремонту", "Ремонт помещения")
    decision = filter_purchase(purchase)
    assert decision.include is False
    assert decision.reason == "service_or_work"


def test_goods_purchase_passes_filter() -> None:
    purchase = _make_purchase("Поставка товара", "Бумага офисная")
    decision = filter_purchase(purchase)
    assert decision.include is True
    assert decision.reason == "ok"


def test_ambiguous_purchase_gets_manual_review_flag() -> None:
    purchase = _make_purchase("Закупка", "Позиция 1")
    decision = filter_purchase(purchase)
    assert decision.include is True
    assert "needs_manual_type_review" in decision.risk_flags
