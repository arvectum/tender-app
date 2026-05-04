from __future__ import annotations

import json
import traceback as tb
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import JobRun
from app.utils.time import utc_now


@dataclass
class JobContext:
    session: Session
    job_run: JobRun


def create_job_run(
    session: Session,
    job_type: str,
    source: str | None = None,
    params_json: dict[str, Any] | None = None,
    status: str = "pending",
) -> JobRun:
    job = JobRun(
        job_type=job_type,
        source=source,
        status=status,
        params_json=_json_safe(params_json),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def mark_running(session: Session, job_run_id: int) -> JobRun:
    job = _get_job(session, job_run_id)
    job.status = "running"
    job.started_at = utc_now()
    session.commit()
    session.refresh(job)
    return job


def mark_success(session: Session, job_run_id: int, result_json: dict[str, Any] | None = None) -> JobRun:
    job = _get_job(session, job_run_id)
    job.status = "success"
    job.finished_at = utc_now()
    job.result_json = _json_safe(result_json)
    _set_duration(job)
    session.commit()
    session.refresh(job)
    return job


def mark_failed(
    session: Session,
    job_run_id: int,
    error_message: str,
    traceback_text: str | None = None,
    result_json: dict[str, Any] | None = None,
) -> JobRun:
    job = _get_job(session, job_run_id)
    job.status = "failed"
    job.finished_at = utc_now()
    job.error_message = error_message[:4000]
    job.traceback = traceback_text
    job.result_json = _json_safe(result_json)
    _set_duration(job)
    session.commit()
    session.refresh(job)
    return job


def mark_skipped(session: Session, job_run_id: int, result_json: dict[str, Any] | None = None) -> JobRun:
    job = _get_job(session, job_run_id)
    job.status = "skipped"
    if job.started_at is None:
        job.started_at = utc_now()
    job.finished_at = utc_now()
    job.result_json = _json_safe(result_json)
    _set_duration(job)
    session.commit()
    session.refresh(job)
    return job


def mark_cancelled(session: Session, job_run_id: int, result_json: dict[str, Any] | None = None) -> JobRun:
    job = _get_job(session, job_run_id)
    job.status = "cancelled"
    job.finished_at = utc_now()
    job.result_json = _json_safe(result_json)
    _set_duration(job)
    session.commit()
    session.refresh(job)
    return job


def get_latest_jobs(session: Session, limit: int = 50) -> list[JobRun]:
    return session.scalars(select(JobRun).order_by(desc(JobRun.created_at)).limit(limit)).all()


def get_job_stats(session: Session) -> dict[str, Any]:
    counts_by_status = dict(session.execute(select(JobRun.status, func.count(JobRun.id)).group_by(JobRun.status)).all())
    counts_by_type = dict(session.execute(select(JobRun.job_type, func.count(JobRun.id)).group_by(JobRun.job_type)).all())
    day_ago = utc_now() - timedelta(hours=24)
    failed_24h = session.scalar(
        select(func.count(JobRun.id)).where(
            JobRun.status == "failed",
            JobRun.created_at >= day_ago,
        )
    )
    return {
        "status_counts": counts_by_status,
        "type_counts": counts_by_type,
        "failed_last_day": int(failed_24h or 0),
    }


def run_job(
    session: Session,
    job_type: str,
    source: str | None,
    params_json: dict[str, Any] | None,
    job_fn,
):
    job = create_job_run(session=session, job_type=job_type, source=source, params_json=params_json)
    try:
        mark_running(session, job.id)
        result = job_fn(job)
        mark_success(session, job.id, result_json=result if isinstance(result, dict) else {"result": str(result)})
        return job, result
    except Exception as exc:  # noqa: BLE001
        mark_failed(
            session,
            job.id,
            error_message=str(exc),
            traceback_text=tb.format_exc(),
        )
        raise


def _get_job(session: Session, job_run_id: int) -> JobRun:
    job = session.scalar(select(JobRun).where(JobRun.id == job_run_id))
    if job is None:
        raise ValueError(f"JobRun id={job_run_id} not found")
    return job


def _set_duration(job: JobRun) -> None:
    if job.started_at is None or job.finished_at is None:
        return
    delta = job.finished_at - job.started_at
    job.duration_seconds = Decimal(str(round(delta.total_seconds(), 3)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)
