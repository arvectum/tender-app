from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ItemCostCalculation, MarketOffer, Purchase, PurchaseItem, Supplier
from app.price_search.base import MarketOfferCandidate
from app.price_search.relevance import calculate_offer_relevance
from app.services.calculation_service import calculate_purchase


def test_blocked_supplier_excluded_from_calculation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        supplier = Supplier(name="ИП Плохой", normalized_name="ип плохой", status="blocked")
        session.add(supplier)
        purchase = Purchase(
            source="mos_portal",
            external_id="SUP-1",
            title="Поставка",
            status="Прием предложений",
            region="Москва",
            max_total_price=Decimal("1000"),
            parsed_at=utc_now(),
        )
        item = PurchaseItem(position_hash="h-sup", item_name="Картридж HP CE410A оригинальный", quantity=Decimal("2"))
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.refresh(item)
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                item_name=item.item_name,
                offer_title="Картридж HP CE410A оригинальный",
                seller_name="ИП Плохой",
                supplier_name="ИП Плохой",
                supplier_status="blocked",
                supplier_id=supplier.id,
                unit_price=Decimal("100"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                relevance_score=Decimal("0.9"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()
        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status in {"no_relevant_offers", "needs_manual_price_search"}


def test_trusted_supplier_gets_match_bonus() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(source="fixture", external_id="SUP-2", title="T")
        item = PurchaseItem(position_hash="h2", item_name="Картридж HP CE410A оригинальный", quantity=Decimal("1"))
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.refresh(item)

        offer = MarketOfferCandidate(
            provider="manual",
            purchase_item_id=item.id,
            title="Картридж HP CE410A оригинальный",
            url=None,
            seller_name="ООО Ромашка",
            region="Москва",
            unit_price=Decimal("100"),
            available_quantity=Decimal("1"),
            delivery_price=Decimal("0"),
            delivery_days=1,
        )
        unknown = calculate_offer_relevance(item, offer, supplier_status="unknown", min_threshold=0.0).score
        trusted = calculate_offer_relevance(item, offer, supplier_status="trusted", min_threshold=0.0).score
        assert trusted > unknown
