"""Dependencias de FastAPI que hacen de guardia global: sesión, rol, reautenticación y escrituras seguras."""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import sessions
from app.auth.errors import ApiError, forbidden, unauthenticated
from app.config import get_settings
from app.db.models import AuthSession, User
from app.db.session import get_db

APP_HEADER = "X-Requested-With"
APP_HEADER_VALUE = "traductor"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Principal:
    user: User
    session: AuthSession
    token: str

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    """Sesión válida (normal o restringida). Cierra la transacción para no retenerla en respuestas largas."""
    token = sessions.read_token(request)
    s = sessions.find(db, token) if token else None
    if s is None or not s.user.active:
        db.rollback()
        raise unauthenticated()
    principal = Principal(user=s.user, session=s, token=token)
    db.commit()
    return principal


def require_user(p: Principal = Depends(current_principal)) -> Principal:
    if p.session.kind != "normal":
        raise ApiError(403, "PASSWORD_CHANGE_REQUIRED", "Cambia tu contraseña temporal para continuar.")
    return p


def require_admin(p: Principal = Depends(require_user)) -> Principal:
    if not p.is_admin:
        raise forbidden()
    return p


def require_recent_reauth(p: Principal = Depends(require_admin)) -> Principal:
    reauth = sessions.aware(p.session.reauth_at)
    if reauth is None or reauth + timedelta(minutes=get_settings().reauth_minutes) < sessions.now():
        raise ApiError(409, "REAUTH_REQUIRED", "Confirma tu contraseña para continuar.")
    return p


def check_origin(request: Request) -> None:
    """Origin exacto y encabezado de la aplicación (sin sesión: también para el login)."""
    if request.method not in UNSAFE:
        return
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin or origin not in get_settings().allowed_origins:
        raise forbidden("Origen no permitido.")
    if request.headers.get(APP_HEADER) != APP_HEADER_VALUE:
        raise forbidden("Solicitud no permitida.")


def verify_write(request: Request, p: Principal = Depends(current_principal)) -> Principal:
    """Origin, encabezado de la aplicación y X-CSRF-Token ligado a la sesión en toda escritura."""
    if request.method in UNSAFE:
        check_origin(request)
        sent = request.headers.get("x-csrf-token") or ""
        if not sent or not hmac.compare_digest(sessions.sha256(sent), p.session.csrf_hash):
            raise ApiError(403, "CSRF_INVALID", "La sesión no es válida para esta acción. Recarga la página.")
    return p


def optional_principal(request: Request, db: Session) -> Principal | None:
    try:
        return current_principal(request, db)
    except ApiError:
        return None
