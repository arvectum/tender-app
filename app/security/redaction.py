from __future__ import annotations

import re
from collections.abc import Mapping


SENSITIVE_KEYS = {
    "database_url",
    "db_password",
    "password",
    "token",
    "secret",
    "telegram_bot_token",
    "http_proxy",
    "https_proxy",
}


def redact_text(value: str) -> str:
    redacted = value
    redacted = re.sub(
        r"(postgres(?:ql(?:\+\w+)?)?://[^:/\s]+:)([^@/\s]+)",
        r"\1***",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(r"(bot)(\d+:[A-Za-z0-9_-]+)", r"\1***", redacted, flags=re.IGNORECASE)
    return redacted


def redact_mapping(data: Mapping[str, object]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in data.items():
        lowered = key.lower()
        if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
            output[key] = "***"
            continue
        if isinstance(value, str):
            output[key] = redact_text(value)
        else:
            output[key] = value
    return output
