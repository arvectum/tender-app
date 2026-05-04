from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Purchase, PurchaseItem
from app.price_search.base import MarketOfferCandidate
from app.price_search.relevance import calculate_offer_relevance


def _item(session: Session, name: str) -> PurchaseItem:
    purchase = Purchase(source="fixture", external_id="P-1", title="t")
    item = PurchaseItem(position_hash=name, item_name=name, quantity=Decimal("1"))
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(item)
    return item


def test_original_not_matched_with_compatible() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = _item(session, "Картридж HP CE410A оригинальный")
        offer = MarketOfferCandidate(
            provider="manual",
            purchase_item_id=item.id,
            title="Картридж HP CE410A совместимый",
            url=None,
            seller_name="S",
            region="Москва",
            unit_price=Decimal("100"),
            available_quantity=Decimal("10"),
            delivery_price=Decimal("0"),
            delivery_days=1,
        )
        rel = calculate_offer_relevance(item, offer, min_threshold=0.78)
        assert rel.is_relevant is False
        assert rel.hard_reject is True


def test_different_article_hard_reject() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = _item(session, "Картридж HP CE410A оригинальный")
        offer = MarketOfferCandidate(
            provider="manual",
            purchase_item_id=item.id,
            title="Картридж HP CE411A оригинальный",
            url=None,
            seller_name="S",
            region="Москва",
            unit_price=Decimal("100"),
            available_quantity=Decimal("10"),
            delivery_price=Decimal("0"),
            delivery_days=1,
        )
        rel = calculate_offer_relevance(item, offer, min_threshold=0.78)
        assert rel.hard_reject is True
        assert rel.hard_reject_reason == "different_article"


def test_different_category_hard_reject() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = _item(session, "Бумага офисная А4")
        offer = MarketOfferCandidate(
            provider="manual",
            purchase_item_id=item.id,
            title="Папка офисная пластиковая",
            url=None,
            seller_name="S",
            region="Москва",
            unit_price=Decimal("100"),
            available_quantity=Decimal("10"),
            delivery_price=Decimal("0"),
            delivery_days=1,
        )
        rel = calculate_offer_relevance(item, offer, min_threshold=0.78)
        assert rel.is_relevant is False
