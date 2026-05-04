from decimal import Decimal

from app.services.quantity_optimizer import optimize_item_cost
from app.services.schemas import OfferSnapshot


def test_quantity_optimizer_picks_min_cost_mix() -> None:
    offers = [
        OfferSnapshot(
            offer_id=1,
            item_name="test",
            supplier_name="A",
            unit_price=Decimal("10"),
            available_quantity=2,
            delivery_price=Decimal("0"),
        ),
        OfferSnapshot(
            offer_id=2,
            item_name="test",
            supplier_name="B",
            unit_price=Decimal("15"),
            available_quantity=20,
            delivery_price=Decimal("0"),
        ),
    ]

    result = optimize_item_cost(
        required_quantity=4,
        offers=offers,
        default_unknown_delivery_cost=Decimal("500"),
    )

    assert result.status == "calculated"
    assert result.covered_quantity == 4
    assert result.estimated_cost == Decimal("50")


def test_quantity_optimizer_marks_insufficient() -> None:
    offers = [
        OfferSnapshot(
            offer_id=1,
            item_name="test",
            supplier_name="A",
            unit_price=Decimal("10"),
            available_quantity=2,
            delivery_price=Decimal("0"),
        )
    ]

    result = optimize_item_cost(
        required_quantity=4,
        offers=offers,
        default_unknown_delivery_cost=Decimal("500"),
    )

    assert result.status == "insufficient_market_quantity"
    assert result.covered_quantity == 2
