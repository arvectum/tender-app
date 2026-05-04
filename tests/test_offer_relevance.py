from decimal import Decimal

from app.models import PurchaseItem
from app.price_search.base import MarketOfferCandidate
from app.price_search.relevance import calculate_offer_relevance


def _item(name: str, description: str | None = None) -> PurchaseItem:
    return PurchaseItem(
        purchase_id=1,
        position_hash="h",
        item_name=name,
        description=description,
        quantity=Decimal("1"),
        unit="шт",
    )


def _offer(title: str) -> MarketOfferCandidate:
    return MarketOfferCandidate(
        provider="test",
        purchase_item_id=1,
        title=title,
        url="https://example.com",
        seller_name="Seller",
        region="Москва",
        unit_price=Decimal("100"),
        available_quantity=Decimal("10"),
        delivery_price=Decimal("0"),
        delivery_days=1,
    )


def test_relevance_high_for_matching_item() -> None:
    item = _item("Картридж HP 305A CE410A черный")
    offer = _offer("Картридж HP 305A CE410A черный оригинальный")

    result = calculate_offer_relevance(item, offer)
    assert result.score >= 0.78
    assert result.is_relevant is True


def test_relevance_low_for_other_item() -> None:
    item = _item("Картридж HP 305A CE410A черный")
    offer = _offer("Стул офисный деревянный")

    result = calculate_offer_relevance(item, offer)
    assert result.score < 0.78
    assert result.is_relevant is False


def test_original_vs_compatible_fails_relevance() -> None:
    item = _item("Картридж HP 305A CE410A оригинальный")
    offer = _offer("Картридж совместимый CE410A аналог")

    result = calculate_offer_relevance(item, offer)
    assert result.is_relevant is False
    assert result.hard_reject is True
    assert result.hard_reject_reason == "compatible_when_original_required"
