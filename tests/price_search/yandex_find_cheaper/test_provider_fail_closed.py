from __future__ import annotations

from decimal import Decimal

from app.price_search.yandex_find_cheaper import provider as provider_module
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


class _FakeAgentWithFallbackHit:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str, limit: int = 10):
        self.calls.append(query)
        if query == "q-primary":
            return [], []
        return [
            {
                "title": "Ноутбук Lenovo ThinkPad",
                "url": "https://vendor.example/product/thinkpad",
                "unit_price": "99999",
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


def test_provider_uses_fallback_query_when_primary_empty(monkeypatch) -> None:
    provider = YandexFindCheaperProvider()
    agent = _FakeAgentWithFallbackHit()
    provider.agent = agent

    monkeypatch.setattr(provider_module, "build_search_queries", lambda _item: ["q-primary", "q-fallback"])

    candidates = provider.search_offers(_FakeItem())

    assert len(candidates) == 1
    assert candidates[0].url == "https://vendor.example/product/thinkpad"
    assert agent.calls == ["q-primary", "q-fallback"]
