"""Esquemas de respuesta (`response_model`) de las rutas de trabajos, ajustes, sesión y cuentas.

Las rutas siguen armando dicts; FastAPI los valida contra estos modelos, filtra lo que no esté declarado y los
describe en `/openapi.json`. El orden de los campos es el de los dicts (el JSON no cambia, ver
`tests/test_response_snapshots.py`) y no se usa `exclude_none`: un `None` sale como `null`. Las fechas van como
texto ISO tal y como las formatea el backend.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class OkOut(BaseModel):
    ok: bool


# ---- trabajos (routes_jobs)

class JobStage(BaseModel):
    key: str
    label: str
    state: Literal["completed", "in_progress", "pending", "error", "cancelled", "paused"]


class ReviewPage(BaseModel):
    page: int
    reasons: list[str]


class JobRead(BaseModel):
    id: int
    mode: Literal["translate", "digitize", "prepare"]
    ocr_lang: str | None
    status: str
    stage: str
    progress: float
    current_page: int | None
    page_count: int
    document_id: int
    original_name: str
    title_es: str | None
    output_name: str | None
    error: str | None
    recomposing: bool
    recompose_error: str | None
    stages: list[JobStage]
    review_pages: list[ReviewPage]


class PageRead(BaseModel):
    number: int
    kind: str
    needs_review: bool
    reasons: list[str]


class PresignBookOut(BaseModel):
    url: str
    key: str
    expires_at: str
    method: Literal["PUT"]
    headers: dict[str, str]


# ---- ajustes (routes_settings)

class SettingsPublic(BaseModel):
    """Vista completa del admin (`RuntimeSettings.public()`): nunca la llave, solo si está y su pista."""
    provider: str
    deepseek_model: str
    deepseek_thinking: str
    deepseek_concurrency: int
    deepseek_key_set: bool
    deepseek_key_hint: str
    deepseek_models: list[str]


class SettingsUserView(BaseModel):
    """Vista del rol user (`RuntimeSettings.method()`, #08). `extra="forbid"` hace que la vista del admin no
    encaje aquí, así la unión `SettingsPublic | SettingsUserView` nunca recorta la respuesta del admin."""
    model_config = ConfigDict(extra="forbid")
    provider: str
    deepseek_model: str


class SettingsTestOut(BaseModel):
    ok: bool
    provider: str
    message: str


# ---- cuentas y sesión (routes_auth, routes_users)

class UserRead(BaseModel):
    """`app.auth.users.public`: sin hash de contraseña."""
    id: int
    email: str
    name: str
    role: Literal["admin", "user"]
    active: bool
    must_change_password: bool
    temp_password_expires_at: str | None
    created_at: str | None
    updated_at: str | None


class SessionInfo(BaseModel):
    kind: Literal["normal", "restricted"]
    expires_at: str
    idle_timeout_minutes: float
    reauth_until: str | None


class SessionView(BaseModel):
    """`routes_auth.session_view`: usuario, CSRF y vencimientos; nunca el token de sesión."""
    user: UserRead
    csrf_token: str
    session: SessionInfo


class UsersPage(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int


class UserWithPassword(BaseModel):
    """Alta o restablecimiento: la contraseña temporal se muestra una sola vez."""
    user: UserRead
    temporary_password: str
