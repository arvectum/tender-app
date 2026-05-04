from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import JobLock
from app.utils.time import utc_now


def acquire_lock(session: Session, lock_name: str, ttl_seconds: int, owner: str | None = None) -> bool:
    cleanup_expired_locks(session)

    existing = session.scalar(select(JobLock).where(JobLock.lock_name == lock_name))
    if existing is not None:
        return False

    now = utc_now()
    lock = JobLock(
        lock_name=lock_name,
        locked_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        owner=owner,
    )
    session.add(lock)
    session.commit()
    return True


def release_lock(session: Session, lock_name: str) -> None:
    session.execute(delete(JobLock).where(JobLock.lock_name == lock_name))
    session.commit()


def cleanup_expired_locks(session: Session) -> int:
    result = session.execute(delete(JobLock).where(JobLock.expires_at <= utc_now()))
    session.commit()
    return int(result.rowcount or 0)
