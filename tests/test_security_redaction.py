from __future__ import annotations

from app.security.redaction import redact_mapping, redact_text


def test_redact_text_masks_db_password_and_bot_token() -> None:
    raw = "postgresql://user:supersecret@localhost:5432/db and bot123:ABCDEF"
    redacted = redact_text(raw)
    assert "supersecret" not in redacted
    assert "ABCDEF" not in redacted


def test_redact_mapping_masks_sensitive_keys() -> None:
    data = {
        "database_url": "postgresql://user:pass@localhost/db",
        "telegram_bot_token": "123:secret",
        "normal": "value",
    }
    out = redact_mapping(data)
    assert out["database_url"] == "***"
    assert out["telegram_bot_token"] == "***"
    assert out["normal"] == "value"
