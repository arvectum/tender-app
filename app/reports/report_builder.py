from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobRun, Purchase, PurchaseCalculation, PurchaseDecisionScore
from app.utils.time import utc_now


@dataclass
class DailyDigest:
    generated_at: str
    new_purchases_24h: int
    calculated_24h: int
    strong_recommend_count: int
    recommend_count: int
    needs_review_count: int
    top_rows: list[dict]
    attention_rows: list[dict]
    failed_jobs: list[dict]


def build_daily_digest(session: Session, limit: int = 10) -> DailyDigest:
    since = utc_now() - timedelta(hours=24)
    new_purchases = session.scalars(select(Purchase.id).where(Purchase.created_at >= since)).all()
    calculated_rows = session.scalars(select(PurchaseCalculation.id).where(PurchaseCalculation.computed_at >= since)).all()
    strong_rows = session.scalars(select(PurchaseDecisionScore.id).where(PurchaseDecisionScore.decision == "strong_recommend")).all()
    rec_rows = session.scalars(select(PurchaseDecisionScore.id).where(PurchaseDecisionScore.decision == "recommend")).all()
    review_rows = session.scalars(select(PurchaseDecisionScore.id).where(PurchaseDecisionScore.decision == "needs_manual_review")).all()

    top = session.execute(
        select(Purchase, PurchaseCalculation, PurchaseDecisionScore)
        .join(PurchaseCalculation, PurchaseCalculation.purchase_id == Purchase.id)
        .join(PurchaseDecisionScore, PurchaseDecisionScore.purchase_id == Purchase.id)
        .where(PurchaseDecisionScore.decision.in_(["strong_recommend", "recommend"]))
        .order_by(PurchaseDecisionScore.score_total.desc())
        .limit(limit)
    ).all()
    top_rows = [
        {
            "external_id": purchase.external_id,
            "source": purchase.source,
            "max_total_price": float(calc.max_total_price),
            "profit_after_tax": float(calc.profit_after_tax),
            "margin_after_tax_percent": float(calc.margin_after_tax_percent),
            "score_total": float(score.score_total),
            "deadline": purchase.submission_deadline.isoformat() if purchase.submission_deadline else None,
            "next_action": score.next_action,
        }
        for purchase, calc, score in top
    ]

    attention = session.execute(
        select(Purchase, PurchaseDecisionScore)
        .join(PurchaseDecisionScore, PurchaseDecisionScore.purchase_id == Purchase.id)
        .where(PurchaseDecisionScore.decision.in_(["needs_manual_review", "reject"]))
        .order_by(PurchaseDecisionScore.updated_at.desc())
        .limit(limit)
    ).all()
    attention_rows = [
        {
            "external_id": purchase.external_id,
            "decision": score.decision,
            "risk_level": score.risk_level,
            "reason": score.decision_reason,
            "next_action": score.next_action,
        }
        for purchase, score in attention
    ]

    failed_jobs = session.scalars(
        select(JobRun).where(JobRun.status == "failed", JobRun.created_at >= since).order_by(JobRun.created_at.desc()).limit(50)
    ).all()
    failed_rows = [
        {
            "job_type": job.job_type,
            "source": job.source,
            "error": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job in failed_jobs
    ]

    return DailyDigest(
        generated_at=utc_now().isoformat(),
        new_purchases_24h=len(new_purchases),
        calculated_24h=len(calculated_rows),
        strong_recommend_count=len(strong_rows),
        recommend_count=len(rec_rows),
        needs_review_count=len(review_rows),
        top_rows=top_rows,
        attention_rows=attention_rows,
        failed_jobs=failed_rows,
    )
