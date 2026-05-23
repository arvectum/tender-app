from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.db import Base
from app.models import MarketOffer, PurchaseItem
from app.price_search.base import MarketOfferCandidate
from app.services.fixture_loader import load_fixtures
from app.services.price_search_service import PriceSearchService


def test_store_candidates_serializes_decimal_in_raw_payload() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        load_fixtures(
            session,
            purchases_path=Path("fixtures/sample_purchases.json"),
            offers_path=Path("fixtures/sample_market_offers.json"),
            reset=True,
        )
        item = session.scalar(
            select(PurchaseItem)
            .options(selectinload(PurchaseItem.purchase))
            .order_by(PurchaseItem.id)
            .limit(1)
        )
        assert item is not None

        candidate = MarketOfferCandidate(
            provider="yandex",
            purchase_item_id=item.id,
            title=item.item_name,
            url="https://example.com/offer",
            seller_name="Test Seller",
            region="Москва",
            unit_price=Decimal("123.45"),
            available_quantity=Decimal("10"),
            delivery_price=Decimal("0"),
            delivery_days=3,
            raw_payload={
                "unit_price": Decimal("123.45"),
                "nested": {"discount": Decimal("1.5")},
                "list": [Decimal("2.2"), {"x": Decimal("3.3")}],
            },
        )

        service = PriceSearchService(session)
        created = service._store_candidates(item, [candidate])
        assert created == 1

        session.commit()

        offer = session.scalar(select(MarketOffer).order_by(MarketOffer.id.desc()).limit(1))
        assert offer is not None
        assert offer.raw_payload is not None
        assert offer.raw_payload["unit_price"] == "123.45"
        assert offer.raw_payload["nested"]["discount"] == "1.5"
        assert offer.raw_payload["list"][0] == "2.2"
        assert offer.raw_payload["list"][1]["x"] == "3.3"
