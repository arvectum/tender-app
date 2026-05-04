from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.services.job_service import create_job_run, mark_failed, mark_running, mark_success


def test_job_run_success_lifecycle() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = create_job_run(session, job_type="parse", source="mos_portal", params_json={"limit": 10})
        assert job.status == "pending"

        running = mark_running(session, job.id)
        assert running.status == "running"
        assert running.started_at is not None

        success = mark_success(session, job.id, result_json={"found": 10})
        assert success.status == "success"
        assert success.finished_at is not None
        assert success.duration_seconds is not None
        assert success.result_json == {"found": 10}


def test_job_run_failed_contains_error_message() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = create_job_run(session, job_type="calculate", source=None, params_json={})
        mark_running(session, job.id)
        failed = mark_failed(session, job.id, error_message="boom")
        assert failed.status == "failed"
        assert failed.error_message == "boom"
        assert failed.finished_at is not None
