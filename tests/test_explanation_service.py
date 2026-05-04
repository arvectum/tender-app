from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ItemCostCalculation, Purchase, PurchaseCalculation, PurchaseItem
from app.services.explanation_service import build_purchase_explanation


def test_explanation_recommended() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(source="fixture", external_id="E-1", title="T", max_total_price=Decimal("1000"), parsed_at=utc_now())
        item = PurchaseItem(position_hash="eh1", item_name="Item", quantity=Decimal("1"))
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.add(
            PurchaseCalculation(
                purchase_id=purchase.id,
                max_total_price=Decimal("1000"),
                estimated_cost=Decimal("600"),
                estimated_profit=Decimal("300"),
                margin_percent=Decimal("30"),
                cash_required=Decimal("600"),
                recommendation_status="ok",
                problematic_items_count=0,
                unknown_delivery_items_count=0,
                attractiveness_score=Decimal("80"),
                vat_amount=Decimal("0"),
                tax_amount=Decimal("100"),
                cost_before_tax=Decimal("600"),
                cost_after_tax=Decimal("600"),
                profit_before_tax=Decimal("400"),
                profit_after_tax=Decimal("300"),
                margin_before_tax_percent=Decimal("40"),
                margin_after_tax_percent=Decimal("30"),
                risk_level="low",
            )
        )
        session.add(
            ItemCostCalculation(
                purchase_id=purchase.id,
                purchase_item_id=item.id,
                status="ok",
                required_quantity=1,
                covered_quantity=1,
                estimated_item_cost=Decimal("100"),
                unknown_delivery_used=False,
                selected_offers=[],
                risk_flags=[],
                calculation_details_json={},
            )
        )
        session.commit()
        exp = build_purchase_explanation(session, purchase.id)
        assert "рекомендована" in exp.summary


def test_explanation_not_recommended() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(source="fixture", external_id="E-2", title="T", max_total_price=Decimal("1000"), parsed_at=utc_now())
        item = PurchaseItem(position_hash="eh2", item_name="Item", quantity=Decimal("1"))
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.add(
            PurchaseCalculation(
                purchase_id=purchase.id,
                max_total_price=Decimal("1000"),
                estimated_cost=Decimal("900"),
                estimated_profit=Decimal("80"),
                margin_percent=Decimal("8"),
                cash_required=Decimal("900"),
                recommendation_status="not_recommended",
                problematic_items_count=1,
                unknown_delivery_items_count=1,
                attractiveness_score=Decimal("10"),
                vat_amount=Decimal("0"),
                tax_amount=Decimal("20"),
                cost_before_tax=Decimal("900"),
                cost_after_tax=Decimal("900"),
                profit_before_tax=Decimal("100"),
                profit_after_tax=Decimal("80"),
                margin_before_tax_percent=Decimal("10"),
                margin_after_tax_percent=Decimal("8"),
                risk_level="high",
            )
        )
        session.commit()
        exp = build_purchase_explanation(session, purchase.id)
        assert "не рекомендована" in exp.summary
