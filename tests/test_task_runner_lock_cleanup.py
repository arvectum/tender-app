from __future__ import annotations

import signal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import JobLock
from app.services.lock_service import acquire_lock
from app.services.task_runner import _lock_fail_safe, _run_with_lock


def test_run_with_lock_releases_lock_on_keyboard_interrupt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        with pytest.raises(KeyboardInterrupt):
            _run_with_lock(
                session=session,
                job_type="search_prices",
                source="yandex",
                params_json={"mode": "yandex"},
                lock_name="search_prices",
                owner="cli",
                fn=lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            )

        assert session.scalar(select(JobLock).where(JobLock.lock_name == "search_prices")) is None


def test_lock_fail_safe_releases_lock_on_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with Session(engine) as session:
        assert acquire_lock(session, lock_name="search_prices", ttl_seconds=60, owner="test") is True

    from app.services import task_runner

    monkeypatch.setattr(task_runner, "SessionLocal", test_session_local)
    monkeypatch.setattr(task_runner.signal, "raise_signal", lambda _signum: None)

    guard = _lock_fail_safe("search_prices")
    guard.__enter__()
    try:
        guard._on_sigterm(signal.SIGTERM, None)
    finally:
        guard.__exit__(None, None, None)

    with Session(engine) as session:
        assert session.scalar(select(JobLock).where(JobLock.lock_name == "search_prices")) is None
