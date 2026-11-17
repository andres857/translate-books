"""Límite de intentos de login persistido en BD (ventana fija por IP, por correo y total)."""
from __future__ import annotations

import math
from datetime import timedelta

from sqlalchemy.orm import Session

from app.auth.sessions import aware, now, sha256
from app.config import get_settings
from app.db.models import AuthRateLimit


def hit(db: Session, buckets: list[tuple[str, int]]) -> int | None:
    """Suma un intento a cada contador. Devuelve los segundos de espera si alguno supera su límite."""
    window = timedelta(minutes=get_settings().login_window_minutes)
    t = now()
    wait = 0
    for key, limit in buckets:
        row = db.get(AuthRateLimit, key)
        if row is None:
            row = AuthRateLimit(bucket=key, window_start=t, count=0)
            db.add(row)
        elif aware(row.window_start) + window <= t:
            row.window_start, row.count = t, 0
        row.count += 1
        if row.count > limit:
            wait = max(wait, math.ceil((aware(row.window_start) + window - t).total_seconds()))
    db.commit()
    return wait or None


def clear(db: Session, key: str) -> None:
    row = db.get(AuthRateLimit, key)
    if row is not None:
        db.delete(row)


def login_buckets(ip: str | None, email: str) -> list[tuple[str, int]]:
    """Contadores de un intento de login. `ip=None`: IP desconocida (detrás de un proxy propio), sin cubo por IP;
    si no, todos los usuarios compartirían el de la IP del proxy."""
    st = get_settings()
    buckets = [(email_bucket(email), st.login_max_per_email), ("global", st.login_max_global)]
    if ip:
        buckets.insert(0, (f"ip:{ip}", st.login_max_per_ip))
    return buckets


def email_bucket(email: str) -> str:
    return f"email:{sha256(email)[:40]}"
