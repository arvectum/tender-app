from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import BusinessRule, ItemCostCalculation, MarketOffer, Purchase, PurchaseItem
from app.services.calculation_service import calculate_purchase


def test_delivery_mode_strict_skips_unknown_delivery_offer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="DEL-1",
            title="Поставка",
            status="Прием предложений",
            region="Москва",
            max_total_price=Decimal("1000"),
            parsed_at=utc_now(),
        )
        item = PurchaseItem(position_hash="h-del", item_name="Бумага А4", quantity=Decimal("2"))
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
                offer_title="Бумага А4",
                seller_name="S",
                supplier_name="S",
                unit_price=Decimal("100"),
                available_quantity=5,
                delivery_price=None,
                delivery_unknown=True,
                relevance_score=Decimal("0.9"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.add(BusinessRule(key="DELIVERY_MODE", value="strict"))
        session.commit()

        calculate_purchase(session, purchase.id)
        calc = session.scalar(select(ItemCostCalculation).where(ItemCostCalculation.purchase_item_id == item.id))
        assert calc is not None
        assert calc.status in {"no_relevant_offers", "needs_manual_price_search"}
