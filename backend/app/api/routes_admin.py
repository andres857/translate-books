"""Administración: resumen de páginas, bloques bilingües, corrección manual y recomposición."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import playground as pg
from app.api.routes_jobs import _job_or_404, job_status
from app.db.models import Job, Page, Segment
from app.db.session import get_db
from app.pipeline.translate import check_translation, plain, sanitize_html

router = APIRouter(prefix="/api/admin", tags=["admin"])

RECOMPOSE_BUSY = "Ya se está recomponiendo una página de este libro: espera a que termine."


def _report(job: Job) -> dict:
    if job.report_path and Path(job.report_path).exists():
        try:
            return json.loads(Path(job.report_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def _segment(s: Segment) -> dict:
    return {"key": s.seg_key, "bbox": s.bbox, "block_type": s.block_type, "action": s.action,
            "source_html": s.source_html or s.source_text, "translation": s.translation,
            "issues": s.issues or [], "fit_scale": s.fit_scale, "ocr_confidence": s.ocr_confidence,
            "edited": bool(s.edited)}


def book_info(job: Job) -> dict:
    """Título, subtítulo y autor para la cabecera. El título traducido suele venir como «Título - Subtítulo».
    El autor sale del nombre del archivo («… (Carole Taylor).pdf»); si no, de los metadatos del PDF."""
    doc = job.document
    full = doc.title_es or doc.title or re.sub(r"\.pdf$", "", doc.original_name, flags=re.I)
    title, _, subtitle = full.partition(" - ")
    author = None
    for group in re.findall(r"\(([^()]+)\)", doc.original_name):
        g = group.strip()
        if g and not re.search(r"[\d.@]|lib", g, re.I) and len(g) <= 80:
            author = g
            break
    if author is None:
        try:
            import pymupdf
            with pymupdf.open(Path(doc.path)) as pdf:
                author = (pdf.metadata or {}).get("author") or None
        except Exception:  # noqa: BLE001
            author = None
    return {"title": title.strip(), "subtitle": subtitle.strip() or None, "author": author,
            "source_lang": "EN", "target_lang": "ES"}


@router.get("/jobs/{job_id}/summary")
def summary(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, None)  # router solo admin
    report = _report(job)
    pages = []
    for p in db.scalars(select(Page).where(Page.job_id == job_id).order_by(Page.number)):
        scales = [s.fit_scale for s in p.segments if s.fit_scale]
        pages.append({"number": p.number, "kind": p.kind, "needs_review": p.needs_review,
                      "reasons": p.review_reasons or [], "segments": len(p.segments),
                      "translated": sum(1 for s in p.segments if s.action == "translate" and s.translation),
                      "edited": sum(1 for s in p.segments if s.edited),
                      "min_scale": round(min(scales), 2) if scales else None})
    review = sum(1 for p in pages if p["needs_review"])
    return {
        "job": job_status(job),
        "book": book_info(job),
        "totals": {"pages": len(pages) or job.document.page_count, "ok": len(pages) - review, "review": review,
                   "by_kind": dict(Counter(p["kind"] for p in pages)),
                   "segments": sum(p["segments"] for p in pages), "edited": sum(p["edited"] for p in pages)},
        "checks": report.get("validaciones", {}),
        "stats": report.get("estadisticas", {}),
        "warnings": report.get("advertencias", []),
        "errors": report.get("errores", []),
        "pages": pages,
    }


def _page_or_404(db: Session, job_id: int, number: int) -> Page:
    page = db.scalars(select(Page).where(Page.job_id == job_id, Page.number == number)).first()
    if page is None:
        raise HTTPException(404, "Esa página no existe o el libro todavía no se ha procesado.")
    return page


@router.get("/jobs/{job_id}/pages/{number}/segments")
def page_segments(job_id: int, number: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id, None)  # router solo admin
    page = _page_or_404(db, job_id, number)
    return {"number": page.number, "width": page.width, "height": page.height, "kind": page.kind,
            "needs_review": page.needs_review, "reasons": page.review_reasons or [],
            "segments": [_segment(s) for s in sorted(page.segments, key=lambda x: (x.bbox[1], x.bbox[0]))]}


@router.get("/jobs/{job_id}/chapters")
def chapters(job_id: int, db: Session = Depends(get_db)):
    """Índice del libro (capítulos y secciones) con el título traducido de cada uno cuando se encuentra."""
    job = _job_or_404(db, job_id, None)  # router solo admin
    return pg.translate_titles(db, job, pg.book_chapters(db, job))


class SegmentEdit(BaseModel):
    translation: str = Field(min_length=1, max_length=20000)


@router.put("/jobs/{job_id}/segments/{seg_key}")
def edit_segment(job_id: int, seg_key: str, body: SegmentEdit, db: Session = Depends(get_db)):
    """Guarda una traducción corregida a mano. No recompone: eso se pide aparte, por página."""
    job = _job_or_404(db, job_id, None)  # router solo admin
    if (job.options or {}).get("mode") == "digitize":
        raise HTTPException(400, "Los libros digitalizados no tienen traducción que corregir.")
    if job.status in ("queued", "running"):
        # el worker reescribe las páginas desde lo que leyó al empezar: la corrección se perdería
        raise HTTPException(409, "El libro se está procesando: espera a que termine para guardar correcciones.")
    seg = db.scalars(select(Segment).join(Page).where(Page.job_id == job_id, Segment.seg_key == seg_key)).first()
    if seg is None:
        raise HTTPException(404, "No encontramos ese bloque.")
    if seg.action not in ("translate", "review"):
        raise HTTPException(400, "Este bloque se conserva tal cual; no tiene traducción editable.")
    text = sanitize_html(body.translation.strip())
    if not plain(text).strip():
        raise HTTPException(400, "La traducción no puede quedar vacía.")
    issues = check_translation(seg.source_html or seg.source_text, text)
    tr_plain = plain(text)
    issues += [f"falta el término protegido «{v}»" for v in (seg.placeholders or {}).values() if v not in tr_plain]
    seg.translation, seg.edited, seg.issues, seg.action = text, True, issues, "translate"
    db.commit()
    return _segment(seg)


@router.post("/jobs/{job_id}/pages/{number}/recompose")
def recompose(job_id: int, number: int, db: Session = Depends(get_db)):
    """Encola la recomposición de una página; la ejecuta el worker."""
    job = _job_or_404(db, job_id, None)  # router solo admin
    options = dict(job.options or {})
    if options.get("mode") == "digitize":
        raise HTTPException(400, "Los libros digitalizados no se recomponen.")
    if job.status in ("queued", "running") and options.get("recompose"):
        # el worker trabaja con las páginas que leyó al empezar: otra petición se perdería en silencio
        raise HTTPException(409, RECOMPOSE_BUSY)
    if job.status != "done" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(409, "El libro tiene que estar terminado para recomponer una página.")
    _page_or_404(db, job_id, number)
    options["recompose"] = sorted(set(options.get("recompose") or []) | {number})
    options.pop("recompose_error", None)
    # solo si sigue 'done': dos peticiones a la vez no pueden encolarse una encima de otra
    if not db.execute(update(Job).where(Job.id == job_id, Job.status == "done").values(
            options=options, status="queued", stage="analyze", progress=0.0, error=None)).rowcount:
        db.rollback()
        raise HTTPException(409, RECOMPOSE_BUSY)
    db.commit()
    db.refresh(job)
    return job_status(job)
