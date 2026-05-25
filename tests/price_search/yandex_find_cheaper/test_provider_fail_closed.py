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
            },
            {
                "title": "Лот на агрегаторе закупок",
                "url": "https://zakupki360.ru/tender/123",
                "unit_price": "900",
            },
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


class _FakeAgentWithInvalidRows:
    def __init__(self, rows):
        self.rows = rows

    def search(self, query: str, limit: int = 10):
        return self.rows, []


class _FakeAgentWithStageWarnings:
    def __init__(self, rows):
        self.rows = rows

    def search(self, query: str, limit: int = 10):
        return self.rows, ["captcha_or_blocked:desktop", "empty_serp:touch", "no_relevant_rows:desktop"]


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


def test_provider_filters_missing_or_invalid_url_rows() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgentWithInvalidRows(
        [
            {"title": "Ноутбук A", "url": "", "unit_price": "1000"},
            {"title": "Ноутбук B", "url": "not-a-url", "unit_price": "1000"},
            {"title": "Ноутбук C", "url": "ftp://vendor.example/item", "unit_price": "1000"},
        ]
    )

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []


def test_provider_filters_non_positive_unit_price() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgentWithInvalidRows(
        [
            {"title": "Ноутбук A", "url": "https://vendor.example/a", "unit_price": "0"},
            {"title": "Ноутбук B", "url": "https://vendor.example/b", "unit_price": "-1"},
        ]
    )

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []


def test_provider_filters_malformed_price_without_exception() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgentWithInvalidRows(
        [
            {"title": "Ноутбук A", "url": "https://vendor.example/a", "unit_price": "abc"},
            {"title": "Ноутбук B", "url": "https://vendor.example/b", "unit_price": "--"},
        ]
    )

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []


def test_provider_collects_stage_counters_for_fail_closed_diagnostics() -> None:
    provider = YandexFindCheaperProvider()
    provider.agent = _FakeAgentWithStageWarnings(
        [
            {"title": "Ноутбук A", "url": "https://market.mosreg.ru/Trade/ViewTrade?id=1", "unit_price": "1000"},
            {"title": "Ноутбук B", "url": "https://vendor.example/b", "unit_price": "abc"},
        ]
    )

    candidates = provider.search_offers(_FakeItem())

    assert candidates == []
    diagnostics = provider.get_last_diagnostics()
    counters = diagnostics["stage_counters"]
    assert counters["blocked_or_captcha"] >= 1
    assert counters["empty_serp"] >= 1
    assert counters["no_relevant_rows"] >= 1
    assert counters["invalid_or_junk_url"] == 1
    assert counters["no_price_signal"] == 1
    assert counters["strict_reject"] == "N/A"
    assert any(str(w).startswith("diagnostics_stage_counters:") for w in diagnostics["warnings"])
