from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Request, Response

from app.config import get_settings


SESSION_COOKIE_NAME = "tsvc_session"
CSRF_COOKIE_NAME = "tsvc_csrf"
SESSION_TTL_SECONDS = 60 * 60 * 12


def create_session_cookie(response: Response, user_id: int, username: str, role: str) -> None:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    token = _sign_payload(payload, settings.dashboard_secret_key)
    csrf_token = secrets.token_urlsafe(24)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_mode == "production",
        max_age=SESSION_TTL_SECONDS,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.app_mode == "production",
        max_age=SESSION_TTL_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)


def get_session_claims(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    payload = _verify_payload(token, settings.dashboard_secret_key)
    if not payload:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def validate_csrf(request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    settings = get_settings()
    if not settings.dashboard_auth_enabled:
        return True
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not csrf_cookie:
        return False
    header_token = request.headers.get("x-csrf-token")
    if header_token and hmac.compare_digest(header_token, csrf_cookie):
        return True
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return False
    return settings.dashboard_base_url in origin


def _sign_payload(payload: dict[str, Any], secret: str) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii")
    sig = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _verify_payload(token: str, secret: str) -> dict[str, Any] | None:
    try:
        b64, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        raw = base64.urlsafe_b64decode(b64.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
