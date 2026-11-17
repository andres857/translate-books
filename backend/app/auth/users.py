"""Operaciones sobre cuentas: alta, cambios protegidos del último admin, reset y bootstrap del admin inicial."""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import events, passwords, sessions
from app.auth.errors import ApiError
from app.config import get_settings
from app.db.models import User

log = logging.getLogger("app.auth")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
ROLES = ("admin", "user")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def public(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "active": u.active,
            "must_change_password": u.must_change_password,
            "temp_password_expires_at": _iso(u.temp_password_expires_at),
            "created_at": _iso(u.created_at), "updated_at": _iso(u.updated_at)}


def _iso(dt) -> str | None:
    return sessions.aware(dt).isoformat() if dt else None


def _temp_expiry():
    return sessions.now() + timedelta(hours=get_settings().temp_password_hours)


def create(db: Session, email: str, name: str, role: str = "user", *, actor_id: int | None = None,
           ip: str | None = None) -> tuple[User, str]:
    """Crea la cuenta con contraseña temporal. Devuelve la contraseña (se muestra una sola vez)."""
    email = normalize_email(email)
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise ApiError(400, "INVALID_EMAIL", "El correo no es válido.")
    if role not in ROLES:
        raise ApiError(400, "INVALID_ROLE", "Rol no válido.")
    temp = passwords.temporary_password()
    user = User(email=email, name=name.strip() or email, role=role, password_hash=passwords.hash_password(temp),
                must_change_password=True, temp_password_expires_at=_temp_expiry(), active=True)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "EMAIL_TAKEN", "Ya existe una cuenta con ese correo.") from None
    events.record(db, "user_created", user_id=user.id, actor_id=actor_id, ip=ip, role=role)
    return user, temp


def reset_password(db: Session, user: User, *, actor_id: int | None = None, ip: str | None = None) -> str:
    temp = passwords.temporary_password()
    user.password_hash = passwords.hash_password(temp)
    user.must_change_password = True
    user.temp_password_expires_at = _temp_expiry()
    sessions.revoke_all(db, user.id)
    events.record(db, "password_reset", user_id=user.id, actor_id=actor_id, ip=ip)
    return temp


def guarded_update(db: Session, user: User, values: dict) -> None:
    """Aplica `values` en un único UPDATE condicional: si el cambio deja sin admin activo, no se aplica
    (atómico en SQLite, sin carreras entre dos administradores)."""
    removes_admin = (values.get("role", user.role) != "admin") or (values.get("active", user.active) is False)
    stmt = update(User).where(User.id == user.id)
    if removes_admin:
        others = (select(func.count()).select_from(User)
                  .where(User.role == "admin", User.active.is_(True), User.id != user.id).scalar_subquery())
        stmt = stmt.where(or_(User.role != "admin", User.active.is_(False), others >= 1))
    values = {**values, "updated_at": sessions.now()}
    if db.execute(stmt.values(**values)).rowcount != 1:
        db.rollback()
        raise ApiError(409, "LAST_ADMIN", "Debe quedar al menos un administrador activo.")
    db.refresh(user)


def ensure_bootstrap_admin(db: Session) -> None:
    """Crea el admin inicial desde el entorno si su correo no existe. Nunca modifica una cuenta existente."""
    st = get_settings()
    email = normalize_email(st.admin_bootstrap_email)
    if not email or not st.admin_bootstrap_password:
        if not db.scalar(select(func.count()).select_from(User)):
            log.warning("No hay usuarios: define ADMIN_BOOTSTRAP_EMAIL y ADMIN_BOOTSTRAP_PASSWORD "
                        "o usa `python -m app.cli auth-recover --email ...`.")
        return
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        return
    err = passwords.policy_error(st.admin_bootstrap_password)
    if err or not EMAIL_RE.match(email):
        log.error("ADMIN_BOOTSTRAP_* no válido, no se crea el admin inicial: %s", err or "correo no válido")
        return
    # la contraseña viene del entorno: obliga a cambiarla en el primer login (sin vencimiento, no se mostró)
    db.add(User(email=email, name=st.admin_bootstrap_name.strip() or "Administrador", role="admin",
                password_hash=passwords.hash_password(st.admin_bootstrap_password), must_change_password=True,
                active=True))
    try:
        db.flush()
    except IntegrityError:  # otro proceso lo creó a la vez
        db.rollback()
        return
    user_id = db.scalar(select(User.id).where(User.email == email))
    events.record(db, "bootstrap_admin_created", user_id=user_id)
    db.commit()
