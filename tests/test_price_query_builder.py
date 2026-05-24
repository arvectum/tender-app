from decimal import Decimal

from app.models import PurchaseItem
from app.price_search.query_builder import build_search_query


def _make_item(name: str, description: str | None = None) -> PurchaseItem:
    return PurchaseItem(
        purchase_id=1,
        position_hash="h",
        item_name=name,
        description=description,
        quantity=Decimal("1"),
        unit="шт",
    )


def test_build_query_removes_supply_words() -> None:
    item = _make_item("Поставка закупка картриджа HP 305A CE410A")
    query = build_search_query(item)
    lowered = query.lower()
    assert "поставка" not in lowered
    assert "закупка" not in lowered


def test_build_query_keeps_model_article() -> None:
    item = _make_item("Поставка картриджа HP 305A CE410A черный, 2 шт.")
    query = build_search_query(item)
    assert "305a" in query.lower()
    assert "ce410a" in query.lower()


def test_build_query_keeps_brand_contains_region_and_excludes_purchase_qty() -> None:
    item = _make_item("Поставка картриджа HP 305A CE410A черный", description="для закупки 10 шт")
    query = build_search_query(item)
    lowered = query.lower()
    assert "hp" in lowered
    assert "москва" in lowered
    assert "10 шт" not in lowered


def test_build_query_adds_procurement_domain_exclusions() -> None:
    item = _make_item("Поставка картриджа HP 305A CE410A")
    query = build_search_query(item)
    lowered = query.lower()
    assert "-site:zakupki.mos.ru" in lowered
    assert "-site:market.mosreg.ru" in lowered
    assert "-site:roseltorg.ru" in lowered
