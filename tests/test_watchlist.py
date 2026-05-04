from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Purchase
from app.services.watchlist_service import WatchlistService


def test_watchlist_status_is_saved_and_updated() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        purchase = Purchase(source="fixture", external_id="W-1", title="T", max_total_price=Decimal("1000"))
        session.add(purchase)
        session.commit()
        session.refresh(purchase)

        service = WatchlistService(session)
        row = service.add(purchase_id=purchase.id, note="Проверить", status="watch")
        assert row.status == "watch"

        row = service.update(purchase_id=purchase.id, status="submitted", note="Отправлено")
        assert row.status == "submitted"
        assert row.note == "Отправлено"
