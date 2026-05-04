from __future__ import annotations

from datetime import UTC, datetime


def calculate_attractiveness_score(
    margin_percent: float,
    estimated_profit: float,
    problematic_items_count: int,
    unknown_delivery_items_count: int,
    submission_deadline: datetime | None,
    now: datetime | None = None,
) -> float:
    reference_now = now or datetime.now(UTC).replace(tzinfo=None)

    score = 50.0
    score += max(min(margin_percent, 80.0), -20.0) * 0.5
    score += min(max(estimated_profit, -50000.0), 300000.0) / 5000.0

    score -= problematic_items_count * 18.0
    score -= unknown_delivery_items_count * 7.0

    if submission_deadline is not None:
        days_left = (submission_deadline - reference_now).total_seconds() / 86400.0
        if days_left < 1:
            score -= 25.0
        elif days_left < 3:
            score -= 12.0
        elif days_left < 7:
            score -= 5.0
        elif days_left > 20:
            score += 4.0

    return round(max(0.0, min(score, 100.0)), 2)
