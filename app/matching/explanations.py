from __future__ import annotations


def format_match_reason(matched_fields: list[str], mismatched_fields: list[str], hard_reject_reason: str | None = None) -> list[str]:
    reasons: list[str] = []
    if matched_fields:
        reasons.append("Совпали поля: " + ", ".join(matched_fields))
    if mismatched_fields:
        reasons.append("Не совпали поля: " + ", ".join(mismatched_fields))
    if hard_reject_reason:
        reasons.append(hard_reject_reason)
    return reasons
