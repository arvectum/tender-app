from __future__ import annotations

from decimal import Decimal
import sys
import types

from app.price_search.yandex_find_cheaper.browser_agent import (
    YandexBrowserAgent,
    _build_fallback_endpoint_plan,
    _build_marketplace_rescue_plan,
    _build_yandex_endpoint_plan,
    _extract_price_from_offer_page,
    _is_blocked_response,
)


def test_endpoint_plan_uses_desktop_then_touch() -> None:
    plan = _build_yandex_endpoint_plan("ноутбук lenovo")

    assert len(plan) == 2
    assert plan[0][0] == "desktop"
    assert "https://yandex.ru/search/?text=" in plan[0][1]
    assert plan[1][0] == "touch"
    assert "https://yandex.ru/search/touch/?text=" in plan[1][1]


def test_fallback_endpoint_plan_contains_ddg_html_then_bing_html() -> None:
    plan = _build_fallback_endpoint_plan("ноутбук lenovo")

    assert len(plan) == 2
    assert plan[0][0] == "ddg_html"
    assert "https://html.duckduckgo.com/html/?q=" in plan[0][1]
    assert plan[1][0] == "bing_html"
    assert "https://www.bing.com/search?q=" in plan[1][1]


def test_marketplace_rescue_plan_contains_wb_ozon_ym() -> None:
    plan = _build_marketplace_rescue_plan("ноутбук lenovo")

    assert [name for name, _ in plan] == ["wb_direct", "ozon_direct", "ym_direct"]
    assert "wildberries.ru" in plan[0][1]
    assert "ozon.ru/search" in plan[1][1]
    assert "market.yandex.ru/search" in plan[2][1]


def test_block_detection_hits_known_markers() -> None:
    assert _is_blocked_response("Нам очень жаль, но запросы похожи на robot traffic") is True
    assert _is_blocked_response("Пожалуйста, введите капча для продолжения") is True


def test_block_detection_does_not_trigger_on_normal_serp_text() -> None:
    assert _is_blocked_response("Нашлось 2 млн результатов. Купить ноутбук в Москве") is False


def test_extract_price_from_offer_page_parses_body_text() -> None:
    class _FakeOfferPage:
        def goto(self, _url: str, *, wait_until: str, timeout: int) -> None:
            assert wait_until == "domcontentloaded"
            assert timeout == 3000

        def inner_text(self, selector: str) -> str:
            assert selector == "body"
            return "Описание товара. Цена: 12 345 ₽. В наличии"

        def close(self) -> None:
            return None

    class _FakeContext:
        def new_page(self) -> _FakeOfferPage:
            return _FakeOfferPage()

    price = _extract_price_from_offer_page(
        _FakeContext(),
        "https://shop.example.com/product/hp-ce410a",
        timeout_ms=3000,
    )

    assert price == Decimal("12345")


def test_ddg_html_search_uses_offer_page_price_when_snippet_has_no_price(monkeypatch) -> None:
    import app.price_search.yandex_find_cheaper.browser_agent as mod

    class _FakePage:
        def __init__(self, body_text: str) -> None:
            self._body_text = body_text

        def goto(self, _url: str, **_kwargs) -> None:
            return None

        def inner_text(self, selector: str) -> str:
            assert selector == "body"
            return self._body_text

        def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self) -> None:
            self._calls = 0

        def new_page(self) -> _FakePage:
            self._calls += 1
            if self._calls == 1:
                return _FakePage("serp page")
            return _FakePage("Товар в наличии. Стоимость 9 990 ₽")

        def close(self) -> None:
            return None

    class _FakeBrowser:
        def new_context(self, **_kwargs) -> _FakeContext:
            return _FakeContext()

        def close(self) -> None:
            return None

    class _FakeChromium:
        def launch(self, **_kwargs) -> _FakeBrowser:
            return _FakeBrowser()

    class _FakePlaywrightCtx:
        def __enter__(self):
            return types.SimpleNamespace(chromium=_FakeChromium())

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setitem(sys.modules, "playwright.sync_api", types.SimpleNamespace(sync_playwright=lambda: _FakePlaywrightCtx()))
    monkeypatch.setattr(mod, "_build_yandex_endpoint_plan", lambda _query: ())
    monkeypatch.setattr(mod, "_build_fallback_endpoint_plan", lambda _query: (("ddg_html", "https://html.duckduckgo.com/html/?q=x"),))
    monkeypatch.setattr(
        mod,
        "_extract_serp_rows",
        lambda _page, endpoint_name="desktop": [
            {
                "title": "Картридж HP CE410A",
                "url": "https://shop.example.com/hp-ce410a",
                "snippet": "Оригинал, в наличии",
            }
        ],
    )

    records, warnings = YandexBrowserAgent().search("HP CE410A купить", limit=5)

    assert records
    assert records[0]["unit_price"] == Decimal("9990")
    assert "price_from_offer_page:ddg_html" in warnings


def test_search_falls_back_to_bing_after_yandex_block_and_ddg_empty(monkeypatch) -> None:
    import app.price_search.yandex_find_cheaper.browser_agent as mod

    class _FakePage:
        def __init__(self, endpoint_name: str) -> None:
            self.endpoint_name = endpoint_name

        def goto(self, _url: str, **_kwargs) -> None:
            return None

        def inner_text(self, selector: str) -> str:
            assert selector == "body"
            if self.endpoint_name == "desktop":
                return "капча robot"
            return "обычная выдача"

        def close(self) -> None:
            return None

    class _FakeContext:
        def __init__(self, endpoint_name: str) -> None:
            self._endpoint_name = endpoint_name

        def new_page(self) -> _FakePage:
            return _FakePage(self._endpoint_name)

        def close(self) -> None:
            return None

    class _FakeBrowser:
        def __init__(self, endpoint_name: str) -> None:
            self._endpoint_name = endpoint_name

        def new_context(self, **_kwargs) -> _FakeContext:
            return _FakeContext(self._endpoint_name)

        def close(self) -> None:
            return None

    class _FakeChromium:
        def __init__(self) -> None:
            self._launch_idx = 0
            self._order = ["desktop", "ddg_html", "bing_html"]

        def launch(self, **_kwargs) -> _FakeBrowser:
            endpoint_name = self._order[self._launch_idx]
            self._launch_idx += 1
            return _FakeBrowser(endpoint_name)

    class _FakePlaywrightCtx:
        def __enter__(self):
            return types.SimpleNamespace(chromium=_FakeChromium())

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def _fake_extract_rows(_page, endpoint_name="desktop"):
        if endpoint_name == "ddg_html":
            return []
        if endpoint_name == "bing_html":
            return [
                {
                    "title": "Картридж HP CE410A",
                    "url": "https://shop.example.com/hp-ce410a",
                    "snippet": "Цена 8 490 ₽ в наличии",
                }
            ]
        return []

    monkeypatch.setitem(sys.modules, "playwright.sync_api", types.SimpleNamespace(sync_playwright=lambda: _FakePlaywrightCtx()))
    monkeypatch.setattr(mod, "_build_yandex_endpoint_plan", lambda _query: (("desktop", "https://yandex.ru/search/?text=x"),))
    monkeypatch.setattr(
        mod,
        "_build_fallback_endpoint_plan",
        lambda _query: (
            ("ddg_html", "https://html.duckduckgo.com/html/?q=x"),
            ("bing_html", "https://www.bing.com/search?q=x&setlang=ru-ru"),
        ),
    )
    monkeypatch.setattr(mod, "_extract_serp_rows", _fake_extract_rows)

    records, warnings = YandexBrowserAgent().search("HP CE410A купить", limit=5)

    assert records
    assert records[0]["unit_price"] == Decimal("8490")
    assert "captcha_or_blocked:desktop" in warnings
    assert "empty_serp:ddg_html" in warnings
    assert "fallback_success:bing_html" in warnings
