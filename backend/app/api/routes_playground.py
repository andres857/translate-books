"""Administración › Prompts y Playground: prompts de producción (solo lectura), borradores y evaluaciones."""
from __future__ import annotations

from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import playground as pg
from app.db.models import Job, PlaygroundRun, PromptDraft
from app.db.session import get_db
from app.pipeline.translate import PROMPTS

router = APIRouter(prefix="/api/admin", tags=["playground"])


@router.get("/prompts")
def prompts():
    return PROMPTS


# ------------------------------------------------------------------ borradores

class DraftIn(BaseModel):
    task: str | None = None
    name: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=40000)


def _draft(d: PromptDraft) -> dict:
    return {"id": d.id, "task": d.task, "name": d.name, "text": d.text,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None}


def _draft_or_404(db: Session, draft_id: int) -> PromptDraft:
    d = db.get(PromptDraft, draft_id)
    if not d:
        raise HTTPException(404, "Borrador no encontrado")
    return d


@router.get("/prompt-drafts")
def list_drafts(db: Session = Depends(get_db)):
    return [_draft(d) for d in db.scalars(select(PromptDraft).order_by(PromptDraft.id))]


@router.post("/prompt-drafts")
def create_draft(body: DraftIn, db: Session = Depends(get_db)):
    if body.task not in pg.TASKS:
        raise HTTPException(400, "Tarea no válida")
    if not (body.name or "").strip() or not (body.text or "").strip():
        raise HTTPException(400, "El borrador necesita nombre y texto")
    d = PromptDraft(task=body.task, name=body.name.strip(), text=body.text)
    db.add(d)
    db.commit()
    return _draft(d)


@router.put("/prompt-drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftIn, db: Session = Depends(get_db)):
    d = _draft_or_404(db, draft_id)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "El nombre no puede quedar vacío")
        d.name = body.name.strip()
    if body.text is not None:
        if not body.text.strip():
            raise HTTPException(400, "El texto no puede quedar vacío")
        d.text = body.text
    db.commit()
    return _draft(d)


@router.delete("/prompt-drafts/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    db.delete(_draft_or_404(db, draft_id))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ libros y capítulos

@router.get("/playground/books")
def books(db: Session = Depends(get_db)):
    jobs = db.scalars(select(Job).where(Job.status == "done").order_by(Job.id.desc())).all()
    return [{"id": j.id, "name": j.document.title_es or j.document.title or j.document.original_name,
             "original_name": j.document.original_name, "page_count": j.document.page_count, "task": pg.job_task(j)}
            for j in jobs]


def _job_done(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.status != "done":
        raise HTTPException(404, "Libro no encontrado o sin terminar")
    return job


@router.get("/playground/books/{job_id}/chapters")
def chapters(job_id: int, db: Session = Depends(get_db)):
    """Capítulos del índice del PDF (marcadores) como rangos de páginas. Vacío si el PDF no tiene índice."""
    job = _job_done(db, job_id)
    count = job.document.page_count
    try:
        with pymupdf.open(Path(job.document.path)) as doc:
            toc = [(lvl, title.strip(), page) for lvl, title, page, *_ in doc.get_toc(simple=False) if page >= 1]
    except Exception:  # noqa: BLE001
        return []
    toc = [t for t in toc if t[0] <= 2]
    out = []
    for i, (lvl, title, start) in enumerate(toc):
        nxt = next((p for lv, _, p in toc[i + 1:] if lv <= lvl and p > start), count + 1)
        end = min(nxt - 1, count, start + pg.MAX_PAGES - 1)
        out.append({"title": title or f"Sección {i + 1}", "level": lvl, "pages": f"{start}-{max(start, end)}"})
    return out


# ------------------------------------------------------------------ ejecuciones

class VariantIn(BaseModel):
    provider: str
    model: str | None = None
    thinking: str | None = None
    effort: str | None = None
    prompt: int | str | None = "production"
    prompt_name: str | None = None


class RunIn(BaseModel):
    job_id: int
    pages: str
    chapter: str | None = None
    variants: list[VariantIn]


def _run(r: PlaygroundRun) -> dict:
    return {"id": r.id, "job_id": r.job_id, "task": r.task, "pages": r.pages, "chapter": r.chapter,
            "variants": r.variants, "status": r.status, "progress": r.progress, "current_variant": r.current_variant,
            "results": r.results, "error": r.error, "created_at": r.created_at.isoformat() if r.created_at else None, "book": None}


def _run_or_404(db: Session, run_id: int) -> PlaygroundRun:
    r = db.get(PlaygroundRun, run_id)
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return r


@router.post("/playground/runs")
def create_run(body: RunIn, db: Session = Depends(get_db)):
    job = _job_done(db, body.job_id)
    task = pg.job_task(job)
    try:
        a, b = pg.parse_pages(body.pages, job.document.page_count)
        variants = pg.validate_variants([v.model_dump() for v in body.variants], task, pg.load_drafts(db))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    names = {d.id: d.name for d in db.scalars(select(PromptDraft))}
    for v in variants:
        if isinstance(v["prompt"], int):
            v["prompt_name"] = names.get(v["prompt"], v["prompt_name"])
    count = len(pg.segment_rows(db, job.id, a, b, task))
    if count == 0:
        raise HTTPException(400, "Esas páginas no tienen bloques para evaluar")
    if count > pg.MAX_SEGMENTS:
        raise HTTPException(400, f"El rango tiene {count} bloques; el máximo es {pg.MAX_SEGMENTS}. Elige menos páginas.")
    r = PlaygroundRun(job_id=job.id, task=task, pages=f"{a}-{b}", chapter=body.chapter, variants=variants,
                      results=[], status="queued", progress=0.0)
    db.add(r)
    db.commit()
    return _run(r)


@router.get("/playground/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.scalars(select(PlaygroundRun).order_by(PlaygroundRun.id.desc()).limit(50)).all()
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_({r.job_id for r in runs})))}
    out = []
    for r in runs:
        d = _run(r)
        d.pop("results")
        job = jobs.get(r.job_id)
        d["book"] = (job.document.title_es or job.document.title or job.document.original_name) if job else None
        out.append(d)
    return out


@router.get("/playground/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = _run_or_404(db, run_id)
    job = db.get(Job, r.job_id)
    a, b = (int(x) for x in r.pages.split("-"))
    d = _run(r)
    d["book"] = job.document.title_es or job.document.title or job.document.original_name
    d["segments"] = [{"key": sg.seg_key, "page": n, "block_type": sg.block_type,
                      "source": sg.source_html or sg.source_text, "production": sg.translation}
                     for n, sg in pg.segment_rows(db, r.job_id, a, b, r.task)]
    return d


@router.post("/playground/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    r = _run_or_404(db, run_id)
    if r.status in ("queued", "running"):
        r.status = "cancelled"
        db.commit()
    return _run(r)
