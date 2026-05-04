from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Purchase, PurchaseItem
from app.services.data_validation_service import DataValidationService
from app.utils.time import utc_now


def test_validate_data_marks_low_quality_for_invalid_purchase() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        purchase = Purchase(
            source="mos_portal",
            external_id="DV-1",
            title="Invalid purchase",
            max_total_price=Decimal("-1"),
            submission_deadline=utc_now() - timedelta(hours=2),
        )
        purchase.items.append(
            PurchaseItem(
                position_hash="dv-hash-1",
                item_name="Broken item",
                quantity=Decimal("0"),
                max_unit_price=Decimal("-10"),
            )
        )
        session.add(purchase)
        session.commit()

        summary = DataValidationService(session).validate()
        refreshed = session.get(Purchase, purchase.id)

    assert summary.checked_purchases == 1
    assert summary.low_quality == 1
    assert refreshed is not None
    assert refreshed.data_quality == "low"
    assert any("deadline is expired" in msg for msg in (refreshed.data_quality_warnings_json or []))
