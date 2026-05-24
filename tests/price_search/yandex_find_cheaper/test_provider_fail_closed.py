from __future__ import annotations

from decimal import Decimal

from app.price_search.yandex_find_cheaper.provider import YandexFindCheaperProvider


class _FakeItem:
    id = 1
    item_name = "Ноутбук"
    description = "Ноутбук офисный"
    quantity = Decimal("1")
    unit = "шт"
    attributes = None


class _FakeAgent:
    def search(self, query: str, limit: int = 10):
        return [], ["captcha_or_blocked"]


class _FakeAgentWithProcurementRows:
    def search(self, query: str, limit: int = 10):
        return [
            {
                "title": "Лот на маркетплейсе закупок",
                "url": "https://market.mosreg.ru/Trade/ViewTrade?id=1",
                "unit_price": "1000",
            }
        ], []


def test_provider_returns_empty_on_blocked_without_candidates() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgent()

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []


def test_provider_filters_procurement_domain_rows() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgentWithProcurementRows()

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []
