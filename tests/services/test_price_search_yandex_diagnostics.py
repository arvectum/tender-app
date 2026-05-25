from __future__ import annotations

from app.services.price_search_service import PriceSearchService, SearchPricesResult
from app.services.task_runner import _result_to_json


def test_derive_needs_manual_reason_priority_blocked_page() -> None:
    reason = PriceSearchService._derive_needs_manual_reason(
        {
            "stage_counters": {
                "blocked_or_captcha": 2,
                "no_price_signal": 5,
                "no_relevant_rows": 1,
            }
        }
    )
    assert reason == "blocked_page"


def test_derive_needs_manual_reason_variants() -> None:
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"no_price_signal": 1}}) == "no_price_found"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"auth_or_session_missing": 1}}) == "auth_or_session_missing"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"no_relevant_rows": 1}}) == "low_relevance"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"parse_empty": 1}}) == "low_relevance"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"fallback_empty": 1}}) == "rescue_exhausted"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {"invalid_or_junk_url": 1}}) == "extraction_failed"
    assert PriceSearchService._derive_needs_manual_reason({"stage_counters": {}}) == "empty"


def test_merge_int_counters_ignores_non_int_values() -> None:
    target = {"no_price_signal": 1}
    PriceSearchService._merge_int_counters(
        target,
        {
            "no_price_signal": 2,
            "strict_reject": "N/A",
            "blocked_or_captcha": 1,
            "boolean_flag": True,
        },
    )
    assert target == {"no_price_signal": 3, "blocked_or_captcha": 1}


def test_search_prices_result_json_contract_contains_new_counters() -> None:
    result = SearchPricesResult(
        mode="yandex",
        processed_items=3,
        created_offers=0,
        needs_manual_items=3,
        needs_manual_reason_counters={"blocked_page": 2, "no_price_found": 1},
        yandex_stage_counters={"blocked_or_captcha": 2, "no_price_signal": 1},
    )

    payload = _result_to_json(result)
    result_json = payload["result"]

    assert result_json["processed_items"] == 3
    assert result_json["created_offers"] == 0
    assert result_json["needs_manual_items"] == 3
    assert result_json["needs_manual_reason_counters"] == {"blocked_page": 2, "no_price_found": 1}
    assert result_json["yandex_stage_counters"] == {"blocked_or_captcha": 2, "no_price_signal": 1}
