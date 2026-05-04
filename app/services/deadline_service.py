from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Purchase, PurchaseDecisionScore, PurchaseWatchlist
from app.services.notification_service import notify_deadline_warning
from app.utils.time import utc_now


def get_deadline_soon_purchases(session: Session, hours: int = 24) -> list[Purchase]:
    now = utc_now()
    until = now + timedelta(hours=hours)
    return session.scalars(
        select(Purchase).where(
            Purchase.submission_deadline.is_not(None),
            Purchase.submission_deadline > now,
            Purchase.submission_deadline <= until,
        )
    ).all()


def get_expired_purchases(session: Session) -> list[Purchase]:
    now = utc_now()
    return session.scalars(
        select(Purchase).where(Purchase.submission_deadline.is_not(None), Purchase.submission_deadline <= now)
    ).all()


def mark_expired(session: Session) -> int:
    rows = get_expired_purchases(session)
    for row in rows:
        row.deadline_status = "expired"
        score = session.scalar(select(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id == row.id))
        if score is not None:
            score.deadline_status = "expired"
    session.commit()
    return len(rows)


def notify_deadlines(session: Session) -> int:
    settings = get_settings()
    if not settings.notify_on_deadline:
        return 0
    warnings = sorted(set(settings.deadline_warning_hours), reverse=True)
    now = utc_now()
    count = 0
    active_watch_statuses = {"watch", "preparing", "submitted"}
    for idx, hours in enumerate(warnings):
        deadline_upper = now + timedelta(hours=hours)
        next_lower = warnings[idx + 1] if idx + 1 < len(warnings) else 0
        deadline_lower = now + timedelta(hours=next_lower)
        purchases = session.scalars(
            select(Purchase)
            .join(PurchaseWatchlist, PurchaseWatchlist.purchase_id == Purchase.id)
            .where(
                Purchase.submission_deadline.is_not(None),
                Purchase.submission_deadline > deadline_lower,
                Purchase.submission_deadline <= deadline_upper,
                PurchaseWatchlist.status.in_(active_watch_statuses),
            )
        ).all()
        for purchase in purchases:
            watch = session.scalar(select(PurchaseWatchlist).where(PurchaseWatchlist.purchase_id == purchase.id))
            score = session.scalar(select(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id == purchase.id))
            margin = score.score_total if score is not None else "-"
            next_action = score.next_action if score and score.next_action else "Проверить закупку вручную."
            message = (
                f"До окончания подачи по закупке №{purchase.external_id} осталось менее {hours}ч. "
                f"Статус: {watch.status if watch else '-'}; score: {margin}. Действие: {next_action}"
            )
            notify_deadline_warning(session=session, purchase_id=purchase.id, hours_left=hours, message=message)
            count += 1
    return count
