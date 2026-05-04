from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobRun
from app.services.calculation_service import calculate_all_purchases, calculate_purchase
from app.services.excel_export_service import export_to_excel
from app.services.fixture_loader import load_fixtures
from app.services.import_service import ImportResult
from app.services.job_service import create_job_run, mark_failed, mark_running, mark_skipped, mark_success
from app.services.lock_service import acquire_lock, release_lock
from app.services.notification_service import notify_failed_job
from app.services.parse_service import parse_and_import
from app.services.price_search_service import PriceSearchService
from app.services.decision_service import DecisionService


DEFAULT_LOCK_TTL = 3600


@dataclass
class JobRunSnapshot:
    id: int
    job_type: str
    source: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    result_json: dict[str, Any] | None
    error_message: str | None


def run_parse_task(
    session: Session,
    source: str,
    status: str,
    limit: int | None,
    dry_run: bool,
    save_raw: bool,
    owner: str,
) -> tuple[Any, Any]:
    lock_name = f"parse:{source}"
    params = {
        "source": source,
        "status": status,
        "limit": limit,
        "dry_run": dry_run,
        "save_raw": save_raw,
    }
    return _run_with_lock(
        session=session,
        job_type="parse",
        source=source,
        params_json=params,
        lock_name=lock_name,
        owner=owner,
        fn=lambda: parse_and_import(
            session=session,
            source=source,
            status=status,
            limit=limit,
            dry_run=dry_run,
            save_raw=save_raw,
        ),
    )


def run_search_prices_task(
    session: Session,
    mode: str,
    limit: int | None,
    purchase_id: int | None,
    item_id: int | None,
    owner: str,
):
    params = {
        "mode": mode,
        "limit": limit,
        "purchase_id": purchase_id,
        "item_id": item_id,
    }
    service = PriceSearchService(session)
    return _run_with_lock(
        session=session,
        job_type="search_prices",
        source=mode,
        params_json=params,
        lock_name="search_prices",
        owner=owner,
        fn=lambda: service.search_prices(mode=mode, limit=limit, purchase_id=purchase_id, item_id=item_id),
    )


def run_calculate_task(session: Session, purchase_id: int | None, owner: str):
    params = {"purchase_id": purchase_id}
    fn = (lambda: calculate_purchase(session, purchase_id)) if purchase_id is not None else (lambda: calculate_all_purchases(session))
    return _run_with_lock(
        session=session,
        job_type="calculate",
        source=None,
        params_json=params,
        lock_name="calculate",
        owner=owner,
        fn=fn,
    )


def run_export_excel_task(session: Session, output_path: Path, owner: str):
    params = {"output_path": str(output_path)}
    return _run_with_lock(
        session=session,
        job_type="export_excel",
        source=None,
        params_json=params,
        lock_name="export_excel",
        owner=owner,
        fn=lambda: export_to_excel(session, output_path=output_path),
    )


def run_evaluate_task(session: Session, purchase_id: int | None, owner: str):
    params = {"purchase_id": purchase_id}
    service = DecisionService(session)
    fn = (lambda: service.evaluate_purchase(purchase_id)) if purchase_id is not None else (lambda: service.evaluate_all())
    return _run_with_lock(
        session=session,
        job_type="evaluate",
        source=None,
        params_json=params,
        lock_name="evaluate",
        owner=owner,
        fn=fn,
    )


def run_import_offers_task(session: Session, file_path: Path, owner: str, importer_fn):
    params = {"file_path": str(file_path)}
    return _run_with_lock(
        session=session,
        job_type="import_offers",
        source="manual",
        params_json=params,
        lock_name="search_prices",
        owner=owner,
        fn=lambda: importer_fn(session, file_path),
    )


def _run_with_lock(
    session: Session,
    job_type: str,
    source: str | None,
    params_json: dict[str, Any],
    lock_name: str,
    owner: str,
    fn,
):
    job = create_job_run(session=session, job_type=job_type, source=source, params_json=params_json)

    locked = acquire_lock(session, lock_name=lock_name, ttl_seconds=DEFAULT_LOCK_TTL, owner=owner)
    if not locked:
        mark_skipped(session, job.id, result_json={"reason": "lock_already_acquired", "lock_name": lock_name})
        return _get_job_snapshot(session, job.id), None

    try:
        mark_running(session, job.id)
        result = fn()
        mark_success(session, job.id, result_json=_result_to_json(result))
        return _get_job_snapshot(session, job.id), result
    except Exception as exc:  # noqa: BLE001
        mark_failed(session, job.id, error_message=str(exc))
        failed_job = _get_job_snapshot(session, job.id)
        notify_failed_job(
            session,
            job.id,
            message=f"Job failed: {failed_job.job_type} source={failed_job.source or '-'} error={exc}",
        )
        raise
    finally:
        release_lock(session, lock_name)


def _result_to_json(result: Any) -> dict[str, Any]:
    if result is None:
        return {"result": None}
    if isinstance(result, dict):
        return result
    if hasattr(result, "__dict__"):
        try:
            return {"result": result.__dict__}
        except Exception:
            return {"result": str(result)}
    return {"result": str(result)}


def _get_job_snapshot(session: Session, job_id: int) -> JobRunSnapshot:
    row = session.scalar(select(JobRun).where(JobRun.id == job_id))
    if row is None:
        raise ValueError(f"JobRun id={job_id} not found")
    return JobRunSnapshot(
        id=row.id,
        job_type=row.job_type,
        source=row.source,
        status=row.status,
        started_at=row.started_at,
        finished_at=row.finished_at,
        result_json=row.result_json,
        error_message=row.error_message,
    )
