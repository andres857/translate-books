"""Purga de datos de login viejos: sesiones cerradas, ventanas de rate limit vencidas y eventos de seguridad.

La caché de traducciones no se toca. Uso: `python -m app.cli purge [--dry-run]`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth.sessions import now
from app.config import get_settings
from app.db.models import AuthRateLimit, AuthSecurityEvent, AuthSession


def _conditions(at: datetime) -> dict:
    st = get_settings()
    sessions_cutoff = at - timedelta(days=st.auth_sessions_retention_days)
    return {
        # revocadas o caducadas hace más de AUTH_SESSIONS_RETENTION_DAYS (la inactividad nunca supera expires_at)
        AuthSession: or_(AuthSession.revoked_at < sessions_cutoff, AuthSession.expires_at < sessions_cutoff),
        # ventana fija vencida: el siguiente intento la reiniciaría a cero de todos modos
        AuthRateLimit: AuthRateLimit.window_start <= at - timedelta(minutes=st.login_window_minutes),
        AuthSecurityEvent: AuthSecurityEvent.created_at < at - timedelta(days=st.auth_events_retention_days),
    }


def purge(db: Session, *, dry_run: bool = False, at: datetime | None = None) -> dict[str, int]:
    """Filas borradas (o que se borrarían con `dry_run`) por tabla. Confirma quien llama."""
    counts: dict[str, int] = {}
    for model, cond in _conditions(at or now()).items():
        name = model.__tablename__
        if dry_run:
            counts[name] = db.scalar(select(func.count()).select_from(model).where(cond)) or 0
        else:
            counts[name] = db.execute(delete(model).where(cond)).rowcount or 0
    return counts
