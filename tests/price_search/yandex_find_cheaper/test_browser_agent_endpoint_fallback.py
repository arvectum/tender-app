from __future__ import annotations

from app.price_search.yandex_find_cheaper.browser_agent import (
    _build_yandex_endpoint_plan,
    _is_blocked_response,
)


def test_endpoint_plan_uses_desktop_then_touch() -> None:
    plan = _build_yandex_endpoint_plan("ноутбук lenovo")

    assert len(plan) == 2
    assert plan[0][0] == "desktop"
    assert "https://yandex.ru/search/?text=" in plan[0][1]
    assert plan[1][0] == "touch"
    assert "https://yandex.ru/search/touch/?text=" in plan[1][1]


def test_block_detection_hits_known_markers() -> None:
    assert _is_blocked_response("Нам очень жаль, но запросы похожи на robot traffic") is True
    assert _is_blocked_response("Пожалуйста, введите капча для продолжения") is True


def test_block_detection_does_not_trigger_on_normal_serp_text() -> None:
    assert _is_blocked_response("Нашлось 2 млн результатов. Купить ноутбук в Москве") is False
