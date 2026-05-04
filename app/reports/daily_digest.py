from __future__ import annotations

from sqlalchemy.orm import Session

from app.reports.report_builder import DailyDigest, build_daily_digest
from app.services.notification_service import notify_daily_digest


def generate_daily_digest(session: Session, send: bool = False) -> DailyDigest:
    digest = build_daily_digest(session)
    if send:
        message = _digest_to_text(digest)
        notify_daily_digest(session=session, message=message)
    return digest


def _digest_to_text(digest: DailyDigest) -> str:
    lines = [
        f"Daily Digest ({digest.generated_at})",
        f"Новых закупок за 24ч: {digest.new_purchases_24h}",
        f"Рассчитано за 24ч: {digest.calculated_24h}",
        f"Strong recommend: {digest.strong_recommend_count}",
        f"Recommend: {digest.recommend_count}",
        f"Needs review: {digest.needs_review_count}",
        "",
        "Top opportunities:",
    ]
    for row in digest.top_rows[:10]:
        lines.append(
            f"- {row['external_id']} | score={row['score_total']} | profit={row['profit_after_tax']} | "
            f"margin={row['margin_after_tax_percent']}% | next={row['next_action']}"
        )
    if digest.failed_jobs:
        lines.append("")
        lines.append("Failed jobs:")
        for job in digest.failed_jobs[:10]:
            lines.append(f"- {job['job_type']} ({job['source'] or '-'}) {job['error']}")
    return "\n".join(lines)
