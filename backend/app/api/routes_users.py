"""Gestión de cuentas (solo admin). Las escrituras exigen reautenticación reciente."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import UserRead, UsersPage, UserWithPassword
from app.auth import events, sessions
from app.auth import users as svc
from app.auth.deps import Principal, require_admin, require_recent_reauth
from app.auth.errors import ApiError
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(default="", max_length=120)
    role: Literal["admin", "user"] = "user"


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")  # el correo no se cambia
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["admin", "user"] | None = None
    active: bool | None = None


def _user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "No encontramos esa cuenta.")
    return user


@router.get("", response_model=UsersPage)
def list_users(page: int = 1, page_size: int = 50, p: Principal = Depends(require_admin),
               db: Session = Depends(get_db)):
    page, page_size = max(1, page), max(1, min(page_size, 200))
    total = db.scalar(select(func.count()).select_from(User))
    rows = db.scalars(select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size))
    return {"items": [svc.public(u) for u in rows], "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=UserWithPassword)
def create_user(body: UserCreate, request: Request, p: Principal = Depends(require_recent_reauth),
                db: Session = Depends(get_db)):
    user, temp = svc.create(db, body.email, body.name, body.role, actor_id=p.user.id, ip=sessions.client_ip(request))
    db.commit()
    return {"user": svc.public(user), "temporary_password": temp}


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, body: UserPatch, request: Request, p: Principal = Depends(require_recent_reauth),
                db: Session = Depends(get_db)):
    user = _user_or_404(db, user_id)
    values = body.model_dump(exclude_none=True)
    if "name" in values:
        values["name"] = values["name"].strip()
        if not values["name"]:
            raise ApiError(400, "INVALID_NAME", "El nombre no puede estar vacío.")
    if user.id == p.user.id and (values.get("role", user.role) != user.role or values.get("active") is False):
        raise ApiError(409, "SELF_CHANGE", "No puedes cambiar tu propio rol ni desactivar tu cuenta.")
    if not values:
        return svc.public(user)
    privileged = values.get("role", user.role) != user.role or values.get("active", user.active) != user.active
    svc.guarded_update(db, user, values)
    if privileged:
        sessions.revoke_all(db, user.id)
    events.record(db, "user_updated", user_id=user.id, actor_id=p.user.id, ip=sessions.client_ip(request),
                  fields=sorted(values))
    db.commit()
    return svc.public(user)


@router.post("/{user_id}/reset-password", response_model=UserWithPassword)
def reset_password(user_id: int, request: Request, p: Principal = Depends(require_recent_reauth),
                   db: Session = Depends(get_db)):
    user = _user_or_404(db, user_id)
    if user.id == p.user.id:
        raise ApiError(409, "SELF_CHANGE", "Para tu propia cuenta usa «Cambiar contraseña».")
    temp = svc.reset_password(db, user, actor_id=p.user.id, ip=sessions.client_ip(request))
    db.commit()
    return {"user": svc.public(user), "temporary_password": temp}
