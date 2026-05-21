from __future__ import annotations

from decimal import Decimal

from app.services.excel_export_service import _is_real_source_url, _resolve_tech_spec_confirmation_status


def test_tech_spec_confirmation_status_green_for_strict_full_match() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand", "model", "category"],
        mismatched_fields=[],
        relevance_score=Decimal("0.40"),
        match_score=Decimal("0.50"),
        margin_percent=Decimal("45"),
    )

    assert status == "green"


def test_tech_spec_confirmation_status_yellow_for_strict_partial_with_low_margin() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand"],
        mismatched_fields=["model"],
        relevance_score=Decimal("1.0"),
        match_score=Decimal("1.0"),
        margin_percent=Decimal("30"),
    )

    assert status == "yellow"


def test_tech_spec_confirmation_status_reject_for_partial_with_high_margin() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand"],
        mismatched_fields=["model"],
        relevance_score=Decimal("1.0"),
        match_score=Decimal("1.0"),
        margin_percent=Decimal("31"),
    )

    assert status == "reject"


def test_tech_spec_confirmation_status_reject_when_no_key_fields() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["trusted_supplier_bonus"],
        mismatched_fields=[],
        relevance_score=Decimal("1.0"),
        match_score=Decimal("1.0"),
        margin_percent=Decimal("10"),
    )

    assert status == "reject"


def test_tech_spec_confirmation_status_reject_when_not_relevant() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=False,
        hard_reject_reason=None,
        matched_fields=["brand", "model"],
        mismatched_fields=[],
        relevance_score=Decimal("1.0"),
        match_score=Decimal("1.0"),
        margin_percent=Decimal("10"),
    )

    assert status == "reject"


def test_is_real_source_url_rejects_placeholder_and_empty() -> None:
    assert _is_real_source_url(None) is False
    assert _is_real_source_url("") is False
    assert _is_real_source_url("https://example.com/offer") is False
    assert _is_real_source_url("https://sub.example.com/offer") is False


def test_is_real_source_url_accepts_real_http_urls() -> None:
    assert _is_real_source_url("https://zakupki.mos.ru/purchase/123") is True
    assert _is_real_source_url("http://supplier.ru/item/1") is True
