
from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ItemCostCalculation, MarketOffer, Purchase, PurchaseCalculation, PurchaseItem
from app.services.calculation_service import calculate_purchase


def _seed_purchase(session: Session, external_id: str = "MOS-10") -> tuple[Purchase, PurchaseItem]:
    purchase = Purchase(
        source="mos_portal",
        external_id=external_id,
        title="Поставка картриджей",
        status="Прием предложений",
        region="Москва",
        max_total_price=Decimal("1000"),
        parsed_at=utc_now(),
    )
    item = PurchaseItem(
        position_external_id="POS-1",
        position_hash=f"hash-{external_id}",
        item_name="Товар X",
        quantity=Decimal("4"),
        unit="шт",
    )
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)
    return purchase, item


def test_calculation_uses_cheapest_and_next_offer_mix() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, external_id="MOS-20")

        session.add_all(
            [
                MarketOffer(
                    provider="manual",
                    source="manual",
                    purchase_id=purchase.id,
                    purchase_item_id=item.id,
                    purchase_external_id=purchase.external_id,
                    position_external_id=item.position_external_id,
                    item_name=item.item_name,
                    offer_title="Товар X",
                    seller_name="A",
                    supplier_name="A",
                    unit_price=Decimal("10"),
                    available_quantity=2,
                    delivery_price=Decimal("0"),
                    effective_unit_price=Decimal("10"),
                    relevance_score=Decimal("0.9"),
                    is_relevant=True,
                    risk_flags=[],
                ),
                MarketOffer(
                    provider="manual",
                    source="manual",
                    purchase_id=purchase.id,
                    purchase_item_id=item.id,
                    purchase_external_id=purchase.external_id,
                    position_external_id=item.position_external_id,
                    item_name=item.item_name,
                    offer_title="Товар X",
                    seller_name="B",
                    supplier_name="B",
                    unit_price=Decimal("15"),
                    available_quantity=20,
                    delivery_price=Decimal("0"),
                    effective_unit_price=Decimal("15"),
                    relevance_score=Decimal("0.95"),
                    is_relevant=True,
                    risk_flags=[],
                ),
            ]
        )
        session.commit()

        calculate_purchase(session, purchase.id)

        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status == "ok"
        assert float(calc.estimated_item_cost) == 50.0
        assert len(calc.selected_offers) == 2


def test_irrelevant_offers_are_not_used() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, external_id="MOS-21")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title="Не тот товар",
                seller_name="X",
                supplier_name="X",
                unit_price=Decimal("10"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                effective_unit_price=Decimal("10"),
                relevance_score=Decimal("0.2"),
                is_relevant=False,
                risk_flags=["low_relevance"],
            )
        )
        session.commit()

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status == "no_relevant_offers"


def test_insufficient_quantity_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, external_id="MOS-22")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title="Товар X",
                seller_name="X",
                supplier_name="X",
                unit_price=Decimal("10"),
                available_quantity=2,
                delivery_price=Decimal("0"),
                effective_unit_price=Decimal("10"),
                relevance_score=Decimal("0.9"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status == "insufficient_market_quantity"


def test_no_offers_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, external_id="MOS-23")

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status in {"no_relevant_offers", "needs_manual_price_search"}


def test_fallback_to_items_max_total_price_when_purchase_total_missing() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase = Purchase(
            source="fixture",
            external_id="MOS-24",
            title="Поставка товара",
            max_total_price=None,
            parsed_at=utc_now(),
        )
        item = PurchaseItem(
            position_external_id="POS-1",
            position_hash="hash-MOS-24",
            item_name="Товар X",
            quantity=Decimal("1"),
            max_total_price=Decimal("300"),
        )
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.refresh(purchase)

        calculate_purchase(session, purchase.id)

        purchase_calc = session.scalar(select(PurchaseCalculation).where(PurchaseCalculation.purchase_id == purchase.id))
        assert purchase_calc is not None
        assert float(purchase_calc.max_total_price) == 300.0
