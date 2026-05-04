from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_session
from app.main import app
from app.models import MarketOffer, Purchase, PurchaseItem
from app.services.user_service import UserService


def _build_client(role: str) -> tuple[TestClient, int, int]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    purchase_id = 0
    offer_id = 0
    with Session(engine) as session:
        user_service = UserService(session)
        user_service.create_user(username=f"{role}_user", email=f"{role}@example.com", role=role, password="Secret123!")

        purchase = Purchase(source="fixture", external_id="A-1", title="T", max_total_price=Decimal("1000"))
        item = PurchaseItem(position_hash="h-1", item_name="Item", quantity=Decimal("1"))
        purchase.items.append(item)
        session.add(purchase)
        session.commit()
        session.refresh(item)

        offer = MarketOffer(
            provider="manual",
            source="manual",
            purchase_id=purchase.id,
            purchase_item_id=item.id,
            item_name=item.item_name,
            offer_title="Item",
            seller_name="Seller",
            supplier_name="Seller",
            unit_price=Decimal("10"),
            available_quantity=1,
            delivery_price=Decimal("0"),
            relevance_score=Decimal("0.9"),
            is_relevant=True,
            risk_flags=[],
        )
        session.add(offer)
        session.commit()
        session.refresh(offer)
        purchase_id = purchase.id
        offer_id = offer.id

    def override_get_session():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    resp = client.post("/login", data={"username": f"{role}_user", "password": "Secret123!"}, follow_redirects=False)
    assert resp.status_code in (303, 307)
    csrf = client.cookies.get("tsvc_csrf")
    assert csrf
    return client, offer_id, purchase_id


def setup_module(module) -> None:  # noqa: ANN001
    import os

    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["APP_MODE"] = "development"
    os.environ["DASHBOARD_AUTH_ENABLED"] = "true"
    os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"
    os.environ["DASHBOARD_ALLOWED_HOSTS"] = "testserver,127.0.0.1,localhost"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru"
    get_settings.cache_clear()


def teardown_module(module) -> None:  # noqa: ANN001
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_viewer_cannot_modify_offer() -> None:
    client, offer_id, purchase_id = _build_client("viewer")
    csrf = client.cookies.get("tsvc_csrf")
    response = client.post(
        f"/offers/{offer_id}/mark-relevant",
        data={"purchase_id": purchase_id},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 403


def test_operator_cannot_manage_users_page() -> None:
    client, _, _ = _build_client("operator")
    response = client.get("/users")
    assert response.status_code == 403


def test_admin_can_manage_users_page() -> None:
    client, _, _ = _build_client("admin")
    response = client.get("/users")
    assert response.status_code == 200
