from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit_log(
    session: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value_json: dict[str, Any] | None = None,
    new_value_json: dict[str, Any] | None = None,
    comment: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_value_json=old_value_json,
        new_value_json=new_value_json,
        comment=comment,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
