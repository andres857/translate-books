"""Copia diaria de la BD SQLite con retención, y purga diaria de datos de login.

Uso: `python -m app.cli backup once` (copia + retención + purga ahora) o `python -m app.cli backup loop`
(servicio `backup` del compose: lo mismo una vez al día a BACKUP_HOUR UTC, y al arrancar si falta la copia de hoy).

La copia usa la API de backup de sqlite3, consistente aunque api y worker estén escribiendo (WAL). Se escribe en
un temporal, se pasa a `journal_mode=DELETE` (un solo archivo, sin -wal/-shm), se comprueba con
`PRAGMA integrity_check` y se renombra a `DATA_DIR/backups/app-AAAA-MM-DD.db` (la de hoy se reemplaza).
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("app.backup")

BACKUP_RE = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.db$")


def db_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise SystemExit(f"Solo se copian BD SQLite (DATABASE_URL={url.split(':', 1)[0]}:…)")
    return Path(url.removeprefix("sqlite:///"))


def backup_name(day: datetime) -> str:
    return f"app-{day:%Y-%m-%d}.db"


def backup_db(src: Path, dest_dir: Path, day: datetime) -> Path:
    """Copia consistente de `src` en `dest_dir/app-<día>.db`. Lanza si la copia no pasa `integrity_check`."""
    if not src.is_file():
        raise FileNotFoundError(src)
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / backup_name(day)
    tmp = final.with_name(final.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(src, timeout=30)) as source, closing(sqlite3.connect(tmp)) as target:
            source.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
            check = target.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"integrity_check de la copia: {check}")
        tmp.replace(final)
    finally:
        tmp.unlink(missing_ok=True)
    return final


def prune(dest_dir: Path, keep: int) -> list[Path]:
    """Borra las copias `app-<fecha>.db` más antiguas y deja las `keep` más recientes. Devuelve las borradas."""
    copies = sorted((p for p in dest_dir.glob("app-*.db") if BACKUP_RE.match(p.name)), key=lambda p: p.name)
    old = copies[: max(len(copies) - max(keep, 1), 0)]
    for p in old:
        p.unlink()
    return old


def run_once(now: datetime | None = None) -> Path:
    """Copia + retención + purga. La purga va después: la copia guarda el estado previo."""
    from app.auth.purge import purge
    from app.db.session import session_scope

    st = get_settings()
    now = now or datetime.now(UTC)
    path = backup_db(db_path(), st.backups_dir, now)
    print(f"copia: {path} ({path.stat().st_size / 1e6:.1f} MB, integrity_check ok)", flush=True)
    for p in prune(st.backups_dir, st.backup_keep):
        print(f"retención ({st.backup_keep}): borrada {p.name}", flush=True)
    with session_scope() as db:
        counts = purge(db)
    print("purga: " + ", ".join(f"{t}: {n} borradas" for t, n in counts.items()), flush=True)
    return path


def next_run(now: datetime, hour: int) -> datetime:
    at = now.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def loop() -> None:
    """Bucle del servicio: si falta la copia de hoy la hace ya; luego duerme hasta BACKUP_HOUR (UTC).

    Duerme en tramos cortos mirando el reloj de pared, para no saltarse la hora tras suspender el equipo.
    Un fallo se registra y se reintenta en la próxima ejecución (no tumba el servicio).
    """
    st = get_settings()
    print(f"servicio de copia: cada día a las {st.backup_hour:02d}:00 UTC, conserva {st.backup_keep} copias "
          f"en {st.backups_dir}", flush=True)

    def attempt() -> None:
        try:
            run_once()
        except Exception:
            log.exception("la copia o la purga falló; se reintenta en la próxima ejecución")

    if not (st.backups_dir / backup_name(datetime.now(UTC))).exists():
        attempt()
    while True:
        due = next_run(datetime.now(UTC), st.backup_hour)
        print(f"próxima ejecución: {due:%Y-%m-%d %H:%M} UTC", flush=True)
        while (left := (due - datetime.now(UTC)).total_seconds()) > 0:
            time.sleep(min(left, 600))
        attempt()
