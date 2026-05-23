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


def test_provider_returns_empty_on_blocked_without_candidates() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgent()

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []
