from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditLog
from app.services.audit_service import write_audit_log


def test_audit_log_created_for_manual_offer_change() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        entry = write_audit_log(
            session=session,
            entity_type="market_offer",
            entity_id="101",
            action="mark_relevant",
            old_value_json={"is_relevant": False},
            new_value_json={"is_relevant": True},
            comment="manual moderation",
        )

        saved = session.scalar(select(AuditLog).where(AuditLog.id == entry.id))
        assert saved is not None
        assert saved.entity_type == "market_offer"
        assert saved.action == "mark_relevant"
        assert saved.old_value_json == {"is_relevant": False}
        assert saved.new_value_json == {"is_relevant": True}
