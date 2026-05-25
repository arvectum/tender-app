from __future__ import annotations

from decimal import Decimal

from app.price_search.yandex_find_cheaper.browser_agent import (
    parse_ruble_price_from_snippet,
    parse_ruble_price_from_title_and_snippet,
)


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


def test_parse_price_from_title_and_snippet_uses_both_sources() -> None:
    assert parse_ruble_price_from_title_and_snippet("Картридж HP", "Цена от 7 890 руб") == Decimal("7890")


def test_parse_price_from_title_and_snippet_does_not_relax_currency_requirement() -> None:
    assert parse_ruble_price_from_title_and_snippet("Картридж 12 345", "Артикул 678") is None


def test_parse_price_rejects_numeric_garbage_not_matching_currency_token() -> None:
    assert parse_ruble_price_from_title_and_snippet("Модель X12345", "SKU 99999 rublesx") is None
