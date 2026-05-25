from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.db import Base
from app.models import MarketOffer, PurchaseItem
import app.services.price_search_service as price_search_service_module
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


def test_manual_mode_relevance_can_recover_from_false() -> None:
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

        offer = MarketOffer(
            provider="yandex",
            source="yandex",
            purchase_id=item.purchase_id,
            purchase_item_id=item.id,
            purchase_external_id=item.purchase.external_id if item.purchase else None,
            position_external_id=item.position_external_id,
            item_name=item.item_name,
            offer_title=item.item_name,
            offer_url="https://example.org/relevance-recovery",
            seller_name="Test Seller",
            supplier_name="Test Seller",
            region="Москва",
            unit_price=Decimal("100"),
            available_quantity=10,
            delivery_price=Decimal("0"),
            delivery_days=3,
            effective_unit_price=Decimal("100"),
            is_relevant=False,
            relevance_score=Decimal("0"),
            risk_flags=[],
            raw_payload={},
            delivery_unknown=False,
            supplier_status="unknown",
        )
        session.add(offer)
        session.flush()

        service = PriceSearchService(session)

        def _always_relevant(*args, **kwargs):
            return SimpleNamespace(
                is_relevant=True,
                score=1.0,
                risk_flags=[],
                reasons=["forced_for_test"],
                matched_fields=["title"],
                mismatched_fields=[],
                hard_reject_reason=None,
            )

        original = price_search_service_module.calculate_offer_relevance
        price_search_service_module.calculate_offer_relevance = _always_relevant
        try:
            result = service._process_manual_mode_item(item)
        finally:
            price_search_service_module.calculate_offer_relevance = original

        assert result == "ok"
        assert offer.is_relevant is True


def test_search_prices_manual_reports_created_offers_count() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        load_fixtures(
            session,
            purchases_path=Path("fixtures/sample_purchases.json"),
            offers_path=Path("fixtures/sample_market_offers.json"),
            reset=True,
        )

        item = session.scalar(select(PurchaseItem).order_by(PurchaseItem.id).limit(1))
        assert item is not None

        offer_1 = MarketOffer(
            provider="manual",
            source="manual",
            purchase_id=item.purchase_id,
            purchase_item_id=item.id,
            purchase_external_id=None,
            position_external_id=item.position_external_id,
            item_name=item.item_name,
            offer_title="Offer 1",
            offer_url="https://example.org/manual-offer-1",
            seller_name="Seller 1",
            supplier_name="Seller 1",
            region="Москва",
            unit_price=Decimal("90"),
            available_quantity=10,
            delivery_price=Decimal("0"),
            delivery_days=1,
            effective_unit_price=Decimal("90"),
            is_relevant=False,
            relevance_score=Decimal("0"),
            risk_flags=[],
            raw_payload={},
            delivery_unknown=False,
            supplier_status="unknown",
        )
        offer_2 = MarketOffer(
            provider="manual",
            source="manual",
            purchase_id=item.purchase_id,
            purchase_item_id=item.id,
            purchase_external_id=None,
            position_external_id=item.position_external_id,
            item_name=item.item_name,
            offer_title="Offer 2",
            offer_url="https://example.org/manual-offer-2",
            seller_name="Seller 2",
            supplier_name="Seller 2",
            region="Москва",
            unit_price=Decimal("95"),
            available_quantity=10,
            delivery_price=Decimal("0"),
            delivery_days=2,
            effective_unit_price=Decimal("95"),
            is_relevant=False,
            relevance_score=Decimal("0"),
            risk_flags=[],
            raw_payload={},
            delivery_unknown=False,
            supplier_status="unknown",
        )
        session.add_all([offer_1, offer_2])
        session.commit()

        offers_count = len(session.scalars(select(MarketOffer.id).where(MarketOffer.purchase_item_id == item.id)).all())
        assert offers_count == 2

        service = PriceSearchService(session)
        result = service.search_prices(mode="manual", item_id=item.id)

        assert result.processed_items == 1
        assert result.needs_manual_items == 0
        assert result.created_offers == offers_count
