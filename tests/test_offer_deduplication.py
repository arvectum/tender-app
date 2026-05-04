from decimal import Decimal

from app.price_search.base import MarketOfferCandidate
from app.price_search.offer_deduplication import deduplicate_offers


def _candidate(url: str, seller: str, unit_price: str, delivery: str, qty: str, score: float) -> MarketOfferCandidate:
    return MarketOfferCandidate(
        provider="test",
        purchase_item_id=1,
        title="Картридж HP",
        url=url,
        seller_name=seller,
        region="Москва",
        unit_price=Decimal(unit_price),
        available_quantity=Decimal(qty),
        delivery_price=Decimal(delivery),
        delivery_days=1,
        relevance_score=score,
    )


def test_deduplication_by_url() -> None:
    first = _candidate("https://example.com/1", "A", "100", "100", "3", 0.9)
    second = _candidate("https://example.com/1", "A", "100", "50", "5", 0.92)

    unique, duplicates = deduplicate_offers([first, second])

    assert len(unique) == 1
    assert len(duplicates) == 1
    assert unique[0].delivery_price == Decimal("50")
