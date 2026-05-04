from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.services.parse_service import parse_and_import


def test_demo_mode_blocks_real_parse(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("REAL_NETWORK_ENABLED", "false")
    monkeypatch.setenv(
        "NO_PROXY",
        "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru",
    )
    get_settings.cache_clear()

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        report = parse_and_import(
            session=session,
            source="mos_portal",
            status="Прием предложений",
            limit=5,
            dry_run=True,
            save_raw=False,
        )
        assert report.results
        assert report.results[0].error_count >= 1

    get_settings.cache_clear()
