from __future__ import annotations

from app.config import get_settings
from app.scheduler import scheduler_status


def test_scheduler_status_reflects_enabled_jobs(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv(
        "NO_PROXY",
        "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru",
    )
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("PARSE_MOS_PORTAL_ENABLED", "true")
    monkeypatch.setenv("PARSE_EAT_ENABLED", "false")
    monkeypatch.setenv("PRICE_SEARCH_ENABLED", "true")
    monkeypatch.setenv("PRICE_SEARCH_MODE", "manual")
    get_settings.cache_clear()

    status = scheduler_status()
    assert status.enabled is True
    assert "parse_mos_portal" in status.configured_jobs
    assert "parse_eat" not in status.configured_jobs
    assert "search_prices" in status.configured_jobs
    assert "calculate" in status.configured_jobs
    assert "export_excel" in status.configured_jobs

    get_settings.cache_clear()
