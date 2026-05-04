from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.models import MarketOffer, Purchase, PurchaseCalculation, PurchaseItem
from app.services.calculation_service import calculate_purchase
from app.services.decision_service import DecisionService
from app.services.financial_check_service import FinancialCheckService
from app.utils.time import utc_now


def test_financial_check_sets_error_for_non_positive_cost() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="FC-1",
            title="Check",
            submission_deadline=utc_now() + timedelta(hours=24),
            max_total_price=Decimal("1000"),
        )
        session.add(purchase)
        session.flush()
        session.add(
            PurchaseCalculation(
                purchase_id=purchase.id,
                max_total_price=Decimal("1000"),
                estimated_cost=Decimal("0"),
                estimated_profit=Decimal("100"),
                margin_percent=Decimal("10"),
                cash_required=Decimal("0"),
                recommendation_status="needs_review",
                problematic_items_count=0,
                unknown_delivery_items_count=0,
                attractiveness_score=Decimal("0"),
                vat_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                cost_before_tax=Decimal("0"),
                cost_after_tax=Decimal("0"),
                profit_before_tax=Decimal("100"),
                profit_after_tax=Decimal("100"),
                margin_before_tax_percent=Decimal("10"),
                margin_after_tax_percent=Decimal("10"),
                risk_level="low",
            )
        )
        session.commit()

        summary = FinancialCheckService(session).check()
        calc = session.scalar(select(PurchaseCalculation).where(PurchaseCalculation.purchase_id == purchase.id))

    assert summary.error_count == 1
    assert calc is not None
    assert calc.financial_check_status == "error"


def test_guardrails_downgrade_strong_recommend_when_data_quality_low(monkeypatch) -> None:
    monkeypatch.setenv("REAL_RUN_MODE", "true")
    get_settings.cache_clear()

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="GR-1",
            title="Guardrail purchase",
            status="Прием предложений",
            region="Москва",
            max_total_price=Decimal("100000"),
            submission_deadline=utc_now() + timedelta(hours=48),
            data_quality="low",
        )
        item = PurchaseItem(position_hash="gr-hash-1", item_name="Item A", quantity=Decimal("1"), unit="шт")
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
                item_name=item.item_name,
                offer_title=item.item_name,
                seller_name="ООО Тест",
                supplier_name="ООО Тест",
                supplier_status="trusted",
                unit_price=Decimal("1000"),
                available_quantity=10,
                delivery_price=Decimal("0"),
                relevance_score=Decimal("0.99"),
                is_relevant=True,
                risk_flags=[],
            )
        )
        session.commit()

        calculate_purchase(session, purchase.id)
        score = DecisionService(session).evaluate_purchase(purchase.id)

        assert score.decision == "needs_manual_review"
        assert score.decision_status == "needs_review"
        assert isinstance(score.explanation_json, dict)

    get_settings.cache_clear()
