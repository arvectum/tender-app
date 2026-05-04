from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ItemCostCalculation, MarketOffer, Purchase, PurchaseItem
from app.services.calculation_service import calculate_purchase


def test_package_quantity_rounds_purchase_up() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="PACK-1",
            title="Поставка",
            status="Прием предложений",
            region="Москва",
            max_total_price=Decimal("2000"),
            parsed_at=utc_now(),
        )
        item = PurchaseItem(position_hash="h-pack", item_name="Стул", quantity=Decimal("3"))
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
                offer_title="Стул офисный",
                seller_name="S",
                supplier_name="S",
                unit_price=Decimal("100"),
                available_quantity=10,
                package_quantity=5,
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
        assert calc.calculation_details_json["overbuy_quantity"] == 2
