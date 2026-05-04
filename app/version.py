from __future__ import annotations

from pathlib import Path


def get_version() -> str:
    root = Path(__file__).resolve().parent.parent
    version_file = root / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"
