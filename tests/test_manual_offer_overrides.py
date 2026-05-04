from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ItemCostCalculation, MarketOffer, Purchase, PurchaseItem
from app.services.calculation_service import calculate_purchase


def _seed_purchase(session: Session, external_id: str) -> tuple[Purchase, PurchaseItem]:
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
        position_external_id=f"{external_id}-pos",
        position_hash=f"hash-{external_id}",
        item_name="Картридж HP 305A",
        quantity=Decimal("4"),
        unit="шт",
    )
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)
    return purchase, item


def test_manual_override_exclude_removes_offer_from_calculation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, "MOS-OVR-1")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title="Картридж HP 305A",
                seller_name="Seller A",
                supplier_name="Seller A",
                unit_price=Decimal("100"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                effective_unit_price=Decimal("100"),
                relevance_score=Decimal("0.95"),
                is_relevant=True,
                manual_override_exclude=True,
                risk_flags=[],
            )
        )
        session.commit()

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status == "no_relevant_offers"


def test_manual_override_include_allows_low_relevance_offer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase, item = _seed_purchase(session, "MOS-OVR-2")
        session.add(
            MarketOffer(
                provider="manual",
                source="manual",
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                purchase_external_id=purchase.external_id,
                position_external_id=item.position_external_id,
                item_name=item.item_name,
                offer_title="Картридж совместимый",
                seller_name="Seller B",
                supplier_name="Seller B",
                unit_price=Decimal("90"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                effective_unit_price=Decimal("90"),
                relevance_score=Decimal("0.20"),
                is_relevant=False,
                manual_override_include=True,
                risk_flags=["low_relevance"],
            )
        )
        session.commit()

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status == "ok"
        assert len(calc.selected_offers) == 1
