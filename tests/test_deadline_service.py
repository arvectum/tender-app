from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Purchase
from app.services.deadline_service import get_deadline_soon_purchases


def test_deadline_service_finds_purchases_less_than_24h() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        soon = Purchase(
            source="fixture",
            external_id="DL-1",
            title="Soon",
            max_total_price=Decimal("1000"),
            submission_deadline=utc_now() + timedelta(hours=3),
        )
        later = Purchase(
            source="fixture",
            external_id="DL-2",
            title="Later",
            max_total_price=Decimal("1000"),
            submission_deadline=utc_now() + timedelta(hours=48),
        )
        session.add_all([soon, later])
        session.commit()

        rows = get_deadline_soon_purchases(session, hours=24)
        ids = {row.external_id for row in rows}
        assert "DL-1" in ids
        assert "DL-2" not in ids
