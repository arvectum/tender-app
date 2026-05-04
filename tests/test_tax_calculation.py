from __future__ import annotations


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import BusinessRule, MarketOffer, Purchase, PurchaseCalculation, PurchaseItem
from app.services.calculation_service import calculate_purchase


def _seed(session: Session, external_id: str = "TAX-1") -> tuple[Purchase, PurchaseItem]:
    purchase = Purchase(
        source="mos_portal",
        external_id=external_id,
        title="Поставка бумаги",
        status="Прием предложений",
        region="Москва",
        max_total_price=Decimal("1000"),
        parsed_at=utc_now(),
    )
    item = PurchaseItem(position_external_id="POS-1", position_hash=f"h-{external_id}", item_name="Бумага А4", quantity=Decimal("4"), unit="шт")
    purchase.items.append(item)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    session.refresh(item)
    session.add(
        MarketOffer(
            provider="manual",
            source="manual",
            purchase_id=purchase.id,
            purchase_item_id=item.id,
            purchase_external_id=purchase.external_id,
            position_external_id=item.position_external_id,
            item_name=item.item_name,
            offer_title="Бумага А4",
            seller_name="S",
            supplier_name="S",
            unit_price=Decimal("100"),
            available_quantity=10,
            delivery_price=Decimal("0"),
            effective_unit_price=Decimal("100"),
            relevance_score=Decimal("0.9"),
            is_relevant=True,
            risk_flags=[],
        )
    )
    session.commit()
    return purchase, item


def test_vat_mode_excluded_adds_vat() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, _ = _seed(session, "TAX-VAT")
        session.add(BusinessRule(key="VAT_MODE", value="excluded"))
        session.add(BusinessRule(key="VAT_RATE", value="20"))
        session.commit()

        calc = calculate_purchase(session, purchase.id)
        assert float(calc.vat_amount) > 0


def test_tax_mode_simplified_income_is_6_percent_revenue() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, _ = _seed(session, "TAX-SI")
        session.add(BusinessRule(key="TAX_MODE", value="simplified_income"))
        session.commit()
        calc = calculate_purchase(session, purchase.id)
        assert float(calc.tax_amount) == 60.0


def test_tax_mode_simplified_income_expense_is_15_percent_profit() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase, _ = _seed(session, "TAX-SIE")
        session.add(BusinessRule(key="TAX_MODE", value="simplified_income_expense"))
        session.commit()
        calc = calculate_purchase(session, purchase.id)
        # revenue=1000, cost=400 => profit_before_tax=600 => tax=90
        assert float(calc.tax_amount) == 90.0
