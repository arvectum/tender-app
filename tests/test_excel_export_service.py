from __future__ import annotations

from decimal import Decimal

from app.services.excel_export_service import _resolve_tech_spec_confirmation_status


def test_tech_spec_confirmation_status_green_for_full_match() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand", "model"],
        mismatched_fields=[],
        relevance_score=Decimal("1.0"),
        match_score=Decimal("1.0"),
        margin_percent=Decimal("45"),
    )

    assert status == "green"


def test_tech_spec_confirmation_status_yellow_for_partial_match_with_low_margin() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand"],
        mismatched_fields=["model"],
        relevance_score=Decimal("0.70"),
        match_score=Decimal("0.80"),
        margin_percent=Decimal("30"),
    )

    assert status == "yellow"


def test_tech_spec_confirmation_status_rejects_when_partial_with_high_margin() -> None:
    status = _resolve_tech_spec_confirmation_status(
        is_relevant=True,
        hard_reject_reason=None,
        matched_fields=["brand"],
        mismatched_fields=["model"],
        relevance_score=Decimal("0.70"),
        match_score=Decimal("0.80"),
        margin_percent=Decimal("31"),
    )

    assert status is None
