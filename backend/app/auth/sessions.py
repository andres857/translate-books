"""Sesiones opacas. El navegador recibe 32 bytes aleatorios en una cookie HttpOnly; la BD guarda su SHA-256.

El token CSRF se deriva del de sesión (HMAC), así `/auth/me` puede devolverlo tras recargar sin guardarlo
en claro; la BD conserva solo su hash para compararlo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuthSession, User

SECURE_COOKIE = "__Host-tl_session"
DEV_COOKIE = "tl_session"
RESTRICTED_MINUTES = 15  # sesión que solo sirve para cambiar la contraseña temporal
TOUCH_EVERY = timedelta(seconds=60)


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; todas se guardan en UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token: str) -> str:
    mac = hmac.new(token.encode(), b"traductor-csrf-v1", hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def cookie_name() -> str:
    return SECURE_COOKIE if get_settings().secure_cookies else DEV_COOKIE


def read_token(request: Request) -> str | None:
    token = request.cookies.get(cookie_name())
    if not token or len(token) > 128:
        return None
    return token


def client_ip(request: Request) -> str:
    return (request.client.host if request.client else "")[:64]


def from_trusted_proxy(request: Request) -> bool:
    """La conexión llega de un proxy propio (TRUSTED_PROXIES): su IP no es la del usuario."""
    import ipaddress

    try:
        ip = ipaddress.ip_address(client_ip(request))
    except ValueError:
        return False
    return any(ip in net for net in get_settings().trusted_proxy_networks)


def idle_expires_at(s: AuthSession) -> datetime:
    return aware(s.last_seen_at) + timedelta(minutes=get_settings().session_idle_minutes)


def is_valid(s: AuthSession | None, at: datetime | None = None) -> bool:
    at = at or now()
    return bool(s and s.revoked_at is None and aware(s.expires_at) > at and idle_expires_at(s) > at)


def create(db: Session, user: User, kind: str, request: Request) -> tuple[AuthSession, str]:
    st = get_settings()
    token = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    t = now()
    expires = t + timedelta(hours=st.session_max_hours)
    if kind == "restricted":
        expires = min(expires, t + timedelta(minutes=RESTRICTED_MINUTES))
        temp_exp = aware(user.temp_password_expires_at)
        if temp_exp:
            expires = min(expires, temp_exp)
    s = AuthSession(token_hash=sha256(token), csrf_hash=sha256(csrf_for(token)), user_id=user.id, kind=kind,
                    created_at=t, last_seen_at=t, expires_at=expires, ip=client_ip(request),
                    user_agent=(request.headers.get("user-agent") or "")[:256])
    db.add(s)
    db.flush()
    return s, token


def find(db: Session, token: str) -> AuthSession | None:
    s = db.scalars(select(AuthSession).where(AuthSession.token_hash == sha256(token))).one_or_none()
    if not is_valid(s):
        return None
    t = now()
    if t - aware(s.last_seen_at) > TOUCH_EVERY:
        s.last_seen_at = t
    return s


def revoke(db: Session, s: AuthSession) -> None:
    if s.revoked_at is None:
        s.revoked_at = now()


def revoke_all(db: Session, user_id: int, except_id: int | None = None) -> int:
    q = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_id is not None:
        q = q.where(AuthSession.id != except_id)
    return db.execute(q.values(revoked_at=now())).rowcount or 0


def set_cookie(response: Response, token: str, s: AuthSession) -> None:
    secure = get_settings().secure_cookies
    max_age = max(0, int((aware(s.expires_at) - now()).total_seconds()))
    response.set_cookie(cookie_name(), token, max_age=max_age, path="/", secure=secure, httponly=True,
                        samesite="strict")


def clear_cookie(response: Response) -> None:
    secure = get_settings().secure_cookies
    response.delete_cookie(cookie_name(), path="/", secure=secure, httponly=True, samesite="strict")
