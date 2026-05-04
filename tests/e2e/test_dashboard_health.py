from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_session
from app.main import app


def test_dashboard_health_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_AUTH_ENABLED", "false")
    monkeypatch.setenv("DASHBOARD_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost")
    monkeypatch.setenv(
        "NO_PROXY",
        "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru",
    )
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "version" in payload
    app.dependency_overrides.clear()
    get_settings.cache_clear()
