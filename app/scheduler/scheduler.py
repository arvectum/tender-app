from __future__ import annotations

from dataclasses import dataclass

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover - depends on optional runtime package
    BlockingScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]

from app.config import get_settings
from app.scheduler.jobs import job_backup, job_calculate, job_daily_digest, job_deadline_check, job_export_excel, job_parse, job_search_prices
from app.utils.logging import get_file_logger


logger = get_file_logger("scheduler", "connectors.log")


@dataclass
class SchedulerStatus:
    enabled: bool
    timezone: str
    configured_jobs: list[str]


_scheduler_started = False


def build_scheduler() -> BlockingScheduler:
    if BlockingScheduler is None:
        raise RuntimeError("APScheduler is not installed. Install it with `pip install apscheduler`.")

    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)

    defaults = {
        "max_instances": settings.scheduler_max_instances,
        "coalesce": settings.scheduler_coalesce,
    }

    if settings.parse_mos_portal_enabled:
        scheduler.add_job(
            job_parse,
            "interval",
            minutes=settings.parse_interval_minutes,
            id="parse_mos_portal",
            kwargs={"source": "mos_portal"},
            **defaults,
        )

    if settings.parse_eat_enabled:
        scheduler.add_job(
            job_parse,
            "interval",
            minutes=settings.parse_interval_minutes,
            id="parse_eat",
            kwargs={"source": "eat"},
            **defaults,
        )

    if settings.price_search_enabled:
        scheduler.add_job(
            job_search_prices,
            "interval",
            minutes=settings.price_search_interval_minutes,
            id="search_prices",
            kwargs={"mode": settings.price_search_mode},
            **defaults,
        )

    scheduler.add_job(
        job_calculate,
        "interval",
        minutes=settings.calculate_interval_minutes,
        id="calculate",
        **defaults,
    )

    scheduler.add_job(
        job_export_excel,
        "interval",
        minutes=settings.export_excel_interval_minutes,
        id="export_excel",
        **defaults,
    )

    scheduler.add_job(
        job_deadline_check,
        "interval",
        minutes=settings.deadline_check_interval_minutes,
        id="deadline_check",
        **defaults,
    )

    if settings.notify_daily_digest:
        if CronTrigger is None:
            raise RuntimeError("APScheduler cron trigger is not available.")
        digest_hour, digest_minute = _parse_daily_digest_time(settings.daily_digest_time)
        scheduler.add_job(
            job_daily_digest,
            CronTrigger(hour=digest_hour, minute=digest_minute, timezone=settings.daily_digest_timezone),
            id="daily_digest",
            **defaults,
        )
    if settings.backup_enabled:
        backup_hour, backup_minute = _parse_daily_digest_time(settings.backup_time)
        scheduler.add_job(
            job_backup,
            CronTrigger(hour=backup_hour, minute=backup_minute, timezone=settings.scheduler_timezone),
            id="backup_db",
            **defaults,
        )

    return scheduler


def run_scheduler() -> None:
    global _scheduler_started
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.info("scheduler is disabled by config")

    scheduler = build_scheduler()
    _scheduler_started = True
    logger.info("scheduler started | timezone=%s", settings.scheduler_timezone)
    scheduler.start()


def scheduler_status() -> SchedulerStatus:
    settings = get_settings()
    jobs: list[str] = []
    if settings.parse_mos_portal_enabled:
        jobs.append("parse_mos_portal")
    if settings.parse_eat_enabled:
        jobs.append("parse_eat")
    if settings.price_search_enabled:
        jobs.append("search_prices")
    jobs.extend(["calculate", "export_excel", "deadline_check"])
    if settings.notify_daily_digest:
        jobs.append("daily_digest")
    if settings.backup_enabled:
        jobs.append("backup_db")
    return SchedulerStatus(
        enabled=settings.scheduler_enabled,
        timezone=settings.scheduler_timezone,
        configured_jobs=jobs,
    )


def is_scheduler_running() -> bool:
    return _scheduler_started


def _parse_daily_digest_time(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        return 9, 0
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return 9, 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return 9, 0
    return hour, minute
