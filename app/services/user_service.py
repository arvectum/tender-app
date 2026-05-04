from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security.password import hash_password, verify_password
from app.utils.time import utc_now


DEFAULT_ROLES = {"admin", "operator", "viewer"}


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_roles(self) -> None:
        for role_name in sorted(DEFAULT_ROLES):
            existing = self.session.scalar(select(Role).where(Role.name == role_name))
            if existing is None:
                self.session.add(Role(name=role_name, description=f"{role_name} role"))
        self.session.commit()

    def create_user(self, username: str, email: str, role: str, password: str | None = None) -> User:
        self.ensure_default_roles()
        if role not in DEFAULT_ROLES:
            raise ValueError(f"Unknown role: {role}")
        if self.session.scalar(select(User).where(User.username == username)) is not None:
            raise ValueError(f"User '{username}' already exists")
        role_row = self.session.scalar(select(Role).where(Role.name == role))
        row = User(
            username=username,
            email=email,
            role=role,
            role_id=role_row.id if role_row else None,
            password_hash=hash_password(password or "ChangeMe123!"),
            is_active=True,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def set_password(self, username: str, password: str) -> User:
        row = self.session.scalar(select(User).where(User.username == username))
        if row is None:
            raise ValueError(f"User '{username}' not found")
        row.password_hash = hash_password(password)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_users(self) -> list[User]:
        return self.session.scalars(select(User).order_by(User.username.asc())).all()

    def set_active(self, username: str, is_active: bool) -> User:
        row = self.session.scalar(select(User).where(User.username == username))
        if row is None:
            raise ValueError(f"User '{username}' not found")
        row.is_active = is_active
        self.session.commit()
        self.session.refresh(row)
        return row

    def authenticate(self, username: str, password: str) -> User | None:
        row = self.session.scalar(select(User).where(User.username == username))
        if row is None or not row.is_active:
            return None
        if not verify_password(password, row.password_hash):
            return None
        row.last_login_at = utc_now()
        self.session.commit()
        self.session.refresh(row)
        return row
