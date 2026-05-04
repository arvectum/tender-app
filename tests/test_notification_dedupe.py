from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.models import DashboardNotification, NotificationLog
from app.services.notification_service import notify_decision_event


def test_notification_logs_prevent_duplicate_event(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv(
        "NO_PROXY",
        "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru",
    )
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "email")
    monkeypatch.setenv("NOTIFY_ON_RECOMMEND", "true")
    get_settings.cache_clear()

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        notify_decision_event(
            session=session,
            purchase_id=100,
            decision="recommend",
            score_total=55.0,
            message="decision update",
        )
        notify_decision_event(
            session=session,
            purchase_id=100,
            decision="recommend",
            score_total=55.0,
            message="decision update",
        )

        sent_logs = session.scalars(select(NotificationLog).where(NotificationLog.status == "sent")).all()
        dashboard_rows = session.scalars(select(DashboardNotification)).all()
        assert len(sent_logs) == 1
        assert len(dashboard_rows) == 1

    get_settings.cache_clear()
