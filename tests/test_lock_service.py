from __future__ import annotations

from datetime import timedelta


from app.utils.time import utc_now

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import JobLock
from app.services.lock_service import acquire_lock, cleanup_expired_locks


def test_lock_prevents_second_parallel_run() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        assert acquire_lock(session, lock_name="calculate", ttl_seconds=60, owner="t1") is True
        assert acquire_lock(session, lock_name="calculate", ttl_seconds=60, owner="t2") is False


def test_cleanup_expired_locks_removes_stale_lock() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        assert acquire_lock(session, lock_name="parse:mos_portal", ttl_seconds=60, owner="t1") is True
        lock = session.scalar(select(JobLock).where(JobLock.lock_name == "parse:mos_portal"))
        assert lock is not None
        lock.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()

        removed = cleanup_expired_locks(session)
        assert removed == 1
        assert session.scalar(select(JobLock).where(JobLock.lock_name == "parse:mos_portal")) is None
