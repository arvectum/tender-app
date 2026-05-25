from __future__ import annotations

from app.price_search.yandex_find_cheaper.browser_agent import (
    _extract_query_core_terms,
    _has_relevance_signal,
)


def test_relevance_signal_accepts_overlap() -> None:
    query_terms = _extract_query_core_terms("HP CE410A купить цена москва -site:zakupki.mos.ru")
    assert _has_relevance_signal(query_terms, "Картридж HP CE410A", "Оригинал в наличии") is True


def test_relevance_signal_rejects_no_overlap() -> None:
    query_terms = _extract_query_core_terms("HP CE410A купить цена")
    assert _has_relevance_signal(query_terms, "Бумага офисная A4", "500 листов") is False
