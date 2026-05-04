from datetime import datetime, timedelta

from app.services.ranking_service import calculate_attractiveness_score


def test_ranking_penalizes_problematic_items() -> None:
    now = datetime(2026, 4, 30, 12, 0, 0)
    clean_score = calculate_attractiveness_score(
        margin_percent=20,
        estimated_profit=15000,
        problematic_items_count=0,
        unknown_delivery_items_count=0,
        submission_deadline=now + timedelta(days=10),
        now=now,
    )
    bad_score = calculate_attractiveness_score(
        margin_percent=20,
        estimated_profit=15000,
        problematic_items_count=2,
        unknown_delivery_items_count=0,
        submission_deadline=now + timedelta(days=10),
        now=now,
    )

    assert clean_score > bad_score


def test_ranking_penalizes_short_deadline() -> None:
    now = datetime(2026, 4, 30, 12, 0, 0)
    long_deadline_score = calculate_attractiveness_score(
        margin_percent=18,
        estimated_profit=9000,
        problematic_items_count=0,
        unknown_delivery_items_count=0,
        submission_deadline=now + timedelta(days=15),
        now=now,
    )
    short_deadline_score = calculate_attractiveness_score(
        margin_percent=18,
        estimated_profit=9000,
        problematic_items_count=0,
        unknown_delivery_items_count=0,
        submission_deadline=now + timedelta(hours=12),
        now=now,
    )

    assert long_deadline_score > short_deadline_score
