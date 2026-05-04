from app.services.calculation_service import pick_recommendation_status


def test_margin_recommended_when_above_threshold_and_no_problems() -> None:
    assert pick_recommendation_status(margin_percent=22.0, min_margin_percent=12.0, problematic_items_count=0) == "ok"


def test_margin_needs_review_when_problematic_items() -> None:
    assert pick_recommendation_status(margin_percent=22.0, min_margin_percent=12.0, problematic_items_count=2) == "needs_review"


def test_margin_not_recommended_when_below_threshold() -> None:
    assert pick_recommendation_status(margin_percent=8.0, min_margin_percent=12.0, problematic_items_count=0) == "not_recommended"
