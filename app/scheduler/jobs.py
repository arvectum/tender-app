from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.reports.daily_digest import generate_daily_digest
from app.services.backup_service import create_backup, cleanup_backups
from app.services.deadline_service import mark_expired, notify_deadlines
from app.services.task_runner import run_calculate_task, run_evaluate_task, run_export_excel_task, run_parse_task, run_search_prices_task
from app.utils.logging import get_file_logger


logger = get_file_logger("scheduler.jobs", "connectors.log")


def job_parse(source: str, status: str = "Прием предложений", limit: int | None = None) -> None:
    with SessionLocal() as session:
        run_parse_task(
            session=session,
            source=source,
            status=status,
            limit=limit,
            dry_run=False,
            save_raw=True,
            owner="scheduler",
        )
    logger.info("scheduler parse job completed | source=%s", source)


def job_search_prices(mode: str, limit: int | None = None) -> None:
    with SessionLocal() as session:
        run_search_prices_task(
            session=session,
            mode=mode,
            limit=limit,
            purchase_id=None,
            item_id=None,
            owner="scheduler",
        )
    logger.info("scheduler search_prices completed | mode=%s", mode)


def job_calculate() -> None:
    with SessionLocal() as session:
        run_calculate_task(session=session, purchase_id=None, owner="scheduler")
        run_evaluate_task(session=session, purchase_id=None, owner="scheduler")
    logger.info("scheduler calculate completed")


def job_export_excel(output_path: Path = Path("exports/tender_small_volume_export.xlsx")) -> None:
    with SessionLocal() as session:
        run_export_excel_task(session=session, output_path=output_path, owner="scheduler")
    logger.info("scheduler export completed | output=%s", output_path)


def job_deadline_check() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        expired_count = mark_expired(session)
        notify_count = notify_deadlines(session)
    logger.info(
        "scheduler deadline check completed | interval=%s min | expired=%s | notified=%s",
        settings.deadline_check_interval_minutes,
        expired_count,
        notify_count,
    )


def job_daily_digest() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        digest = generate_daily_digest(session=session, send=True)
    logger.info(
        "scheduler daily digest completed | time=%s | timezone=%s | top=%s | failed_jobs=%s",
        settings.daily_digest_time,
        settings.daily_digest_timezone,
        len(digest.top_rows),
        len(digest.failed_jobs),
    )


def job_backup() -> None:
    settings = get_settings()
    if not settings.backup_enabled:
        return
    path = create_backup()
    cleanup_stats = cleanup_backups(settings.backup_keep_last)
    logger.info("scheduler backup completed | file=%s | removed=%s", path, cleanup_stats["removed"])
