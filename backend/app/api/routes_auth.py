"""Login, identidad, logout, reautenticación y cambio de contraseña."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import events, passwords, rate_limit, sessions
from app.auth.deps import Principal, check_origin, current_principal, require_admin, verify_write
from app.auth.errors import ApiError
from app.auth.users import normalize_email, public
from app.config import get_settings
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID = "Correo o contraseña incorrectos."
TOO_MANY = "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


class PasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)
    new_password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


def session_view(p_user: User, s, token: str) -> dict:
    """Lo que el frontend guarda en memoria: usuario, CSRF y vencimientos. Nunca el token de sesión."""
    st = get_settings()
    reauth = sessions.aware(s.reauth_at)
    return {
        "user": public(p_user),
        "csrf_token": sessions.csrf_for(token),
        "session": {
            "kind": s.kind,
            "expires_at": sessions.aware(s.expires_at).isoformat(),
            "idle_timeout_minutes": st.session_idle_minutes,
            "reauth_until": (reauth + timedelta(minutes=st.reauth_minutes)).isoformat()
            if reauth else None,
        },
    }


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    email = normalize_email(body.email)
    ip = sessions.client_ip(request)
    wait = rate_limit.hit(db, rate_limit.login_buckets(ip, email))
    if wait:
        events.record(db, "login_rate_limited", ip=ip)
        db.commit()
        raise ApiError(429, "TOO_MANY_ATTEMPTS", TOO_MANY, headers={"Retry-After": str(wait)})

    user = db.scalar(select(User).where(User.email == email))
    ok = passwords.verify_password(user.password_hash if user else None, body.password)
    temp_exp = sessions.aware(user.temp_password_expires_at) if user else None
    expired = bool(user and user.must_change_password and temp_exp and temp_exp <= sessions.now())
    if not ok or not user.active or expired:
        reason = "bad_password" if not ok else "inactive" if not user.active else "temp_expired"
        events.record(db, "login_failed", user_id=user.id if user else None, ip=ip, reason=reason)
        db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", INVALID)

    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(body.password)
    kind = "restricted" if user.must_change_password else "normal"
    s, token = sessions.create(db, user, kind, request)
    rate_limit.clear(db, rate_limit.email_bucket(email))
    events.record(db, "login", user_id=user.id, ip=ip, kind=kind)
    db.commit()
    sessions.set_cookie(response, token, s)
    return session_view(user, s, token)


@router.get("/me")
def me(p: Principal = Depends(current_principal)):
    return session_view(p.user, p.session, p.token)


@router.post("/logout")
def logout(request: Request, response: Response, p: Principal = Depends(verify_write),
           db: Session = Depends(get_db)):
    s = db.merge(p.session)
    sessions.revoke(db, s)
    events.record(db, "logout", user_id=p.user.id, ip=sessions.client_ip(request))
    db.commit()
    sessions.clear_cookie(response)
    return {"ok": True}


@router.post("/reauthenticate")
def reauthenticate(body: PasswordIn, request: Request, p: Principal = Depends(require_admin),
                   _w: Principal = Depends(verify_write), db: Session = Depends(get_db)):
    ip = sessions.client_ip(request)
    wait = rate_limit.hit(db, [(f"reauth:{p.user.id}", get_settings().login_max_per_email)])
    if wait:
        raise ApiError(429, "TOO_MANY_ATTEMPTS", TOO_MANY, headers={"Retry-After": str(wait)})
    user = db.get(User, p.user.id)
    if not passwords.verify_password(user.password_hash, body.password):
        events.record(db, "reauth_failed", user_id=user.id, ip=ip)
        db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "La contraseña no es correcta.")
    s = db.merge(p.session)
    s.reauth_at = sessions.now()
    rate_limit.clear(db, f"reauth:{p.user.id}")
    events.record(db, "reauth", user_id=user.id, ip=ip)
    db.commit()
    return session_view(user, s, p.token)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, response: Response,
                    p: Principal = Depends(verify_write), db: Session = Depends(get_db)):
    """Funciona con sesión normal o restringida. Revoca todas las sesiones y abre una normal nueva."""
    ip = sessions.client_ip(request)
    wait = rate_limit.hit(db, [(f"chpw:{p.user.id}", get_settings().login_max_per_email)])
    if wait:
        raise ApiError(429, "TOO_MANY_ATTEMPTS", TOO_MANY, headers={"Retry-After": str(wait)})
    user = db.get(User, p.user.id)
    if not passwords.verify_password(user.password_hash, body.current_password):
        events.record(db, "password_change_failed", user_id=user.id, ip=ip)
        db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "La contraseña actual no es correcta.")
    err = passwords.policy_error(body.new_password, user.email)
    if err:
        raise ApiError(400, "WEAK_PASSWORD", err)
    if body.new_password == body.current_password:
        raise ApiError(400, "WEAK_PASSWORD", "La contraseña nueva debe ser distinta de la actual.")
    user.password_hash = passwords.hash_password(body.new_password)
    user.must_change_password = False
    user.temp_password_expires_at = None
    user.password_changed_at = sessions.now()
    sessions.revoke_all(db, user.id)
    s, token = sessions.create(db, user, "normal", request)
    rate_limit.clear(db, f"chpw:{p.user.id}")
    events.record(db, "password_changed", user_id=user.id, ip=ip)
    db.commit()
    sessions.set_cookie(response, token, s)
    return session_view(user, s, token)
