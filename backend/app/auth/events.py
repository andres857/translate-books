"""Bitácora de seguridad (tabla auth_security_events + log). Nunca recibe contraseñas, tokens ni CSRF."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import AuthSecurityEvent

log = logging.getLogger("app.auth")


def record(db: Session, type: str, *, user_id: int | None = None, actor_id: int | None = None,
           ip: str | None = None, **detail) -> None:
    """Añade el evento a la sesión de BD (lo confirma quien llama)."""
    db.add(AuthSecurityEvent(type=type, user_id=user_id, actor_id=actor_id, ip=ip, detail=detail))
    log.info("auth %s user=%s actor=%s ip=%s %s", type, user_id, actor_id, ip, detail or "")
