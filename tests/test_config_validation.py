from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import app.cli as cli_module
from app.config import ConfigValidationError, get_settings, validate_settings
from app.db import Base


def test_validate_settings_rejects_invalid_security_mode() -> None:
    settings = get_settings()
    invalid = replace(settings, security_mode="invalid_mode")
    with pytest.raises(ConfigValidationError, match="SECURITY_MODE"):
        validate_settings(invalid)


def test_doctor_reports_no_proxy_error(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    monkeypatch.setattr(cli_module, "SessionLocal", SessionLocal)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.setenv("SECURITY_MODE", "standard")
    monkeypatch.setenv("PRICE_SEARCH_MODE", "manual")
    monkeypatch.setenv("RUN_ALL_PRICE_SEARCH_MODE", "manual")
    get_settings.cache_clear()

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["doctor"])

    assert result.exit_code == 1
    assert "NO_PROXY" in result.output
    assert "zakupki.mos.ru" in result.output

    get_settings.cache_clear()
