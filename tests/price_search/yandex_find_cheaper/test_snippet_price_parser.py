from __future__ import annotations

from decimal import Decimal

from app.price_search.yandex_find_cheaper.browser_agent import parse_ruble_price_from_snippet


def test_parse_price_ruble_sign_with_space_groups() -> None:
    assert parse_ruble_price_from_snippet("Цена: 12 345 ₽") == Decimal("12345")


def test_parse_price_with_ot_prefix_and_rub_word() -> None:
    assert parse_ruble_price_from_snippet("Стоимость от 12 345 руб за шт") == Decimal("12345")


def test_parse_price_with_fractional_kopecks() -> None:
    assert parse_ruble_price_from_snippet("В наличии: 12 345,00 р.") == Decimal("12345.00")


def test_parse_price_returns_none_without_currency_marker() -> None:
    assert parse_ruble_price_from_snippet("Артикул 12 345, модель 678") is None


def test_parse_price_returns_none_for_non_price_text() -> None:
    assert parse_ruble_price_from_snippet("Скидка 50% до 31.12.2026") is None
