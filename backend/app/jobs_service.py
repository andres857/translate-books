"""Reglas compartidas de los trabajos: quién puede verlos y cómo se borran con sus archivos."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import playground as pg
from app.auth.deps import Principal
from app.db.models import Job, PlaygroundRun

PROCESSING_BUSY = "El libro se está procesando: detenlo antes de eliminarlo."
PLAYGROUND_BUSY = "Hay una evaluación del Playground en curso con este libro: espera o cancélala."


def _can_see(p: Principal, job: Job) -> bool:
    return p.is_admin or (job.owner_id is not None and job.owner_id == p.user.id)


def get_visible_job(db: Session, job_id: int, p: Principal | None) -> Job:
    """El trabajo si existe y el usuario puede verlo (el admin ve todos; un user solo los suyos).
    Para un user, el trabajo de otro responde igual que uno inexistente. `p=None` solo desde routers que ya
    exigen admin (routes_admin)."""
    job = db.get(Job, job_id)
    if not job or (p is not None and not _can_see(p, job)):
        raise HTTPException(404, "No encontramos ese trabajo.")
    return job


def ensure_not_busy(db: Session, job: Job, playground_busy: str = PLAYGROUND_BUSY) -> None:
    """409 si el trabajo se está procesando o si hay una evaluación del Playground en curso con él."""
    if job.status in ("queued", "running"):
        raise HTTPException(409, PROCESSING_BUSY)
    busy = db.scalar(select(func.count(PlaygroundRun.id)).where(
        PlaygroundRun.job_id == job.id, PlaygroundRun.status.in_(("queued", "running"))))
    if busy:
        raise HTTPException(409, playground_busy)


def delete_job_and_files(db: Session, job: Job) -> None:
    """Borra el trabajo con todo lo suyo (ver `playground.delete_job`) y, tras el commit, sus archivos."""
    removed = pg.delete_job(db, job)
    db.commit()
    for path in removed:  # después del commit: si la BD falla, los archivos siguen ahí
        pg.remove_path(path)
