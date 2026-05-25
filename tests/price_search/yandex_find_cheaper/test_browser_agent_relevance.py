from __future__ import annotations

from app.price_search.yandex_find_cheaper.browser_agent import (
    _calculate_relevance_score,
    _extract_query_core_terms,
    _has_relevance_signal,
    _is_junk_offer_url,
)


def test_relevance_signal_accepts_overlap() -> None:
    query_terms = _extract_query_core_terms("HP CE410A купить цена москва -site:zakupki.mos.ru")
    assert _has_relevance_signal(query_terms, "Картридж HP CE410A", "Оригинал в наличии") is True


def test_relevance_signal_rejects_no_overlap() -> None:
    query_terms = _extract_query_core_terms("HP CE410A купить цена")
    assert _has_relevance_signal(query_terms, "Бумага офисная A4", "500 листов") is False


def test_extract_query_core_terms_handles_hyphen_sku_and_mixed_script() -> None:
    terms = _extract_query_core_terms("Kyocera TK-5240K tk/5240k ТК-5240К купить цена")
    assert "5240k" in terms
    assert "5240" in terms
    assert "tk" in terms


def test_calculate_relevance_score_prefers_higher_overlap() -> None:
    query_terms = _extract_query_core_terms("hp ce410a 305a картридж")
    strong = _calculate_relevance_score(query_terms, "Картридж HP CE410A 305A", "Оригинальный")
    weak = _calculate_relevance_score(query_terms, "Картридж HP", "Офисный товар")
    assert strong > weak
    assert strong > 0


def test_junk_offer_url_patterns_are_filtered() -> None:
    assert _is_junk_offer_url("https://yabs.yandex.ru/count/abc") is True
    assert _is_junk_offer_url("https://yandex.ru/clck/jsredir?from=yandex") is True
    assert _is_junk_offer_url("https://shop.example.com/product/hp-ce410a") is False
