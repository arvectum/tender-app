from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    # Keep naive UTC datetime for compatibility with timezone=False SQLAlchemy columns.
    return datetime.now(timezone.utc).replace(tzinfo=None)

