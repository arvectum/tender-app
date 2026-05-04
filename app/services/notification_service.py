from __future__ import annotations

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DashboardNotification, NotificationLog
from app.utils.time import utc_now


def notify_recommended_purchase(
    session: Session,
    purchase_id: int,
    margin_percent: float,
    estimated_profit: float,
    message: str,
) -> None:
    settings = get_settings()
    if not settings.notifications_enabled or not settings.notify_on_recommended:
        return
    if margin_percent < settings.notify_min_margin_percent:
        return
    if estimated_profit < settings.notify_min_profit_amount:
        return
    _notify_event(
        session=session,
        event_type="recommended_purchase",
        entity_type="purchase",
        entity_id=str(purchase_id),
        message=message,
        title="Recommended purchase",
        dashboard=True,
    )


def notify_decision_event(session: Session, purchase_id: int, decision: str, score_total: float, message: str) -> None:
    settings = get_settings()
    if not settings.notifications_enabled:
        _dashboard_only(session, event_type=f"decision_{decision}", entity_type="purchase", entity_id=str(purchase_id), title=decision, message=message)
        return

    if decision == "strong_recommend" and not settings.notify_on_strong_recommend:
        return
    if decision == "recommend" and not settings.notify_on_recommend:
        return
    if decision == "needs_manual_review" and not settings.notify_on_needs_review:
        return

    event_type = "new_strong_recommend" if decision == "strong_recommend" else ("new_recommend" if decision == "recommend" else "needs_review")
    _notify_event(
        session=session,
        event_type=event_type,
        entity_type="purchase",
        entity_id=str(purchase_id),
        message=message,
        title=f"{decision} (score {score_total})",
        dashboard=True,
    )


def notify_deadline_warning(session: Session, purchase_id: int, hours_left: int, message: str) -> None:
    settings = get_settings()
    if not settings.notify_on_deadline:
        return
    _notify_event(
        session=session,
        event_type="deadline_warning",
        entity_type="purchase",
        entity_id=f"{purchase_id}:{hours_left}",
        message=message,
        title="Deadline warning",
        dashboard=True,
    )


def notify_failed_job(session: Session, job_id: int, message: str) -> None:
    settings = get_settings()
    if not settings.notifications_enabled or not settings.notify_on_failed_job:
        _dashboard_only(session, event_type="job_failed", entity_type="job_run", entity_id=str(job_id), title="Job failed", message=message)
        return
    _notify_event(
        session=session,
        event_type="job_failed",
        entity_type="job_run",
        entity_id=str(job_id),
        message=message,
        title="Job failed",
        dashboard=True,
    )


def notify_daily_digest(session: Session, message: str) -> None:
    settings = get_settings()
    if not settings.notifications_enabled or not settings.notify_daily_digest:
        return
    _notify_event(
        session=session,
        event_type="daily_digest",
        entity_type="report",
        entity_id=utc_now().strftime("%Y-%m-%d"),
        message=message,
        title="Daily digest",
        dashboard=True,
    )


def _notify_event(
    session: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    message: str,
    title: str,
    dashboard: bool = False,
) -> None:
    settings = get_settings()
    channels = [channel.lower() for channel in settings.notification_channels]

    if _event_already_sent(session, event_type=event_type, entity_type=entity_type, entity_id=entity_id):
        return

    if dashboard:
        _dashboard_only(session, event_type=event_type, entity_type=entity_type, entity_id=entity_id, title=title, message=message)

    for channel in channels:
        if channel == "telegram":
            _send_telegram(session, event_type, entity_type, entity_id, message)
        elif channel == "email":
            _send_email_stub(session, event_type, entity_type, entity_id, message)


def _event_already_sent(session: Session, event_type: str, entity_type: str, entity_id: str) -> bool:
    row = session.scalar(
        select(NotificationLog.id).where(
            NotificationLog.event_type == event_type,
            NotificationLog.entity_type == entity_type,
            NotificationLog.entity_id == entity_id,
            NotificationLog.status == "sent",
        )
    )
    return row is not None


def _dashboard_only(session: Session, event_type: str, entity_type: str, entity_id: str, title: str, message: str) -> None:
    already = session.scalar(
        select(DashboardNotification.id).where(
            DashboardNotification.event_type == event_type,
            DashboardNotification.entity_type == entity_type,
            DashboardNotification.entity_id == entity_id,
            DashboardNotification.status == "unread",
        )
    )
    if already is not None:
        return
    session.add(
        DashboardNotification(
            event_type=event_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            status="unread",
        )
    )
    session.commit()


def _send_telegram(session: Session, event_type: str, entity_type: str, entity_id: str, message: str) -> None:
    settings = get_settings()
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    log = NotificationLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        channel="telegram",
        status="pending",
        message=message,
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    if not token or not chat_id:
        log.status = "failed"
        log.error_message = "telegram settings not configured"
        session.commit()
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        log.status = "sent"
        log.sent_at = utc_now()
        log.error_message = None
    except Exception as exc:  # noqa: BLE001
        log.status = "failed"
        log.error_message = str(exc)

    session.commit()


def _send_email_stub(session: Session, event_type: str, entity_type: str, entity_id: str, message: str) -> None:
    # MVP stub: record as sent to keep flow deterministic and testable.
    log = NotificationLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        channel="email",
        status="sent",
        message=message,
        sent_at=utc_now(),
    )
    session.add(log)
    session.commit()
