from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import JobRun, Purchase, PurchaseCalculation, PurchaseDecisionScore
from app.reports.report_builder import build_daily_digest


def test_daily_digest_contains_top_rows_and_failed_jobs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="R-1",
            title="Поставка бумаги",
            max_total_price=Decimal("100000"),
            submission_deadline=utc_now() + timedelta(hours=48),
        )
        session.add(purchase)
        session.commit()
        session.refresh(purchase)

        session.add(
            PurchaseCalculation(
                purchase_id=purchase.id,
                max_total_price=Decimal("100000"),
                estimated_cost=Decimal("70000"),
                estimated_profit=Decimal("25000"),
                margin_percent=Decimal("25"),
                cash_required=Decimal("70000"),
                recommendation_status="ok",
                problematic_items_count=0,
                unknown_delivery_items_count=0,
                attractiveness_score=Decimal("50"),
                vat_amount=Decimal("0"),
                tax_amount=Decimal("3000"),
                cost_before_tax=Decimal("70000"),
                cost_after_tax=Decimal("70000"),
                profit_before_tax=Decimal("30000"),
                profit_after_tax=Decimal("25000"),
                margin_before_tax_percent=Decimal("30"),
                margin_after_tax_percent=Decimal("25"),
            )
        )
        session.add(
            PurchaseDecisionScore(
                purchase_id=purchase.id,
                decision="recommend",
                risk_level="low",
                score_total=Decimal("55"),
                score_margin=Decimal("20"),
                score_profit=Decimal("10"),
                score_deadline=Decimal("10"),
                score_data_quality=Decimal("20"),
                score_supplier_quality=Decimal("10"),
                score_competition=Decimal("5"),
                score_cash_efficiency=Decimal("10"),
                score_risk=Decimal("10"),
                next_action="Проверить и подать",
                deadline_status="active",
            )
        )
        session.add(
            JobRun(
                job_type="parse",
                source="mos_portal",
                status="failed",
                error_message="network error",
                created_at=utc_now(),
            )
        )
        session.commit()

        digest = build_daily_digest(session, limit=10)
        assert digest.recommend_count >= 1
        assert len(digest.top_rows) >= 1
        assert digest.top_rows[0]["external_id"] == "R-1"
        assert len(digest.failed_jobs) >= 1
