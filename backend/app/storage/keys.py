"""Claves de objeto: <carpeta>/<yyyy>/<mm>/<uuid>.<ext>, sin nombres de usuario ni caracteres raros."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
_SAFE = re.compile(r"[^a-z0-9]")


def generate_key(folder: str, content_type: str, now: datetime | None = None) -> str:
    folder = "/".join(p for p in (_SAFE.sub("-", s.lower()).strip("-") for s in folder.split("/")) if p) or "files"
    now = now or datetime.now(timezone.utc)
    ext = EXT_BY_MIME.get(content_type, "bin")
    return f"{folder}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}.{ext}"
