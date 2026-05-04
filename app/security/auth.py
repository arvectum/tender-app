from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.security.permissions import ADMIN
from app.security.sessions import get_session_claims


class AuthError(HTTPException):
    pass


@dataclass
class CurrentUser:
    id: int
    username: str
    role: str
    is_active: bool


def get_current_user(request: Request, session: Session) -> CurrentUser | None:
    settings = get_settings()
    if not settings.dashboard_auth_enabled:
        return CurrentUser(id=0, username="local-dev", role=ADMIN, is_active=True)

    claims = get_session_claims(request)
    if not claims:
        return None
    user = session.scalar(select(User).where(User.id == int(claims.get("sub", 0))))
    if user is None or not user.is_active:
        return None
    return CurrentUser(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


def require_roles(
    request: Request,
    session: Session,
    roles: set[str],
    api_mode: bool = False,
) -> CurrentUser:
    user = get_current_user(request, session)
    if user is None:
        raise AuthError(status_code=401, detail="Authentication required")
    if user.role not in roles:
        raise AuthError(status_code=403, detail="Forbidden")
    return user
