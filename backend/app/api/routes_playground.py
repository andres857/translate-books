"""Administración › Prompts y Playground: prompts de producción (solo lectura), borradores y evaluaciones."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import pymupdf
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import playground as pg
from app.db.models import Job, Page, PlaygroundAttempt, PlaygroundRun, PromptDraft, Segment
from app.db.session import get_db
from app.pipeline.translate import PROMPTS, TAG_RE

router = APIRouter(prefix="/api/admin", tags=["playground"])


@router.get("/prompts")
def prompts():
    return PROMPTS


# ------------------------------------------------------------------ borradores

class DraftIn(BaseModel):
    task: Literal["translate", "correct"] | None = None  # pg.TASKS
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
    blocks = dict(db.execute(select(Page.job_id, func.count(Segment.id)).join(Segment.page)
                             .where(Page.job_id.in_([j.id for j in jobs]), Segment.action == "translate")
                             .group_by(Page.job_id)).all())
    return [{"id": j.id, "name": j.document.title_es or j.document.title or j.document.original_name,
             "original_name": j.document.original_name, "page_count": j.document.page_count, "task": pg.job_task(j),
             "prepared": (j.options or {}).get("mode") == "prepare", "blocks": blocks.get(j.id, 0),
             "production": bool(j.output_path) and Path(j.output_path).exists()}
            for j in jobs]


@router.delete("/playground/books/{job_id}")
def delete_book(job_id: int, db: Session = Depends(get_db)):
    """Elimina un libro del playground y todo lo de su análisis: páginas y bloques, evaluaciones con su
    historial y PDFs, y la salida en disco. Si el documento no tiene otro análisis, también se borra
    (con su glosario y términos propios, y el PDF subido si ningún otro documento lo comparte)."""
    job = _job_done(db, job_id)
    busy = db.scalar(select(func.count(PlaygroundRun.id)).where(
        PlaygroundRun.job_id == job.id, PlaygroundRun.status.in_(("queued", "running"))))
    if busy:
        raise HTTPException(409, "Hay una evaluación en curso con este libro: espera a que termine o cancélala.")
    removed = pg.delete_job(db, job)
    db.commit()
    for path in removed:  # después del commit: si la BD falla, los archivos siguen ahí
        pg.remove_path(path)
    return {"ok": True}


def _job_done(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job or job.status != "done":
        raise HTTPException(404, "Libro no encontrado o sin terminar")
    return job


@router.get("/playground/books/{job_id}/chapters")
def chapters(job_id: int, db: Session = Depends(get_db)):
    """Capítulos del índice del PDF (marcadores) como rangos de páginas. Sin índice, se detectan por los títulos."""
    return pg.book_chapters(db, _job_done(db, job_id))


@router.get("/playground/books/{job_id}/pages")
def book_pages(job_id: int, db: Session = Depends(get_db)):
    """Páginas del libro para el selector de alcance: tipo (digital, escaneada…) y bloques extraídos de cada una.
    Las páginas que el análisis no guardó (sin texto) salen con tipo vacío y cero bloques."""
    job = _job_done(db, job_id)
    count = pg.book_pages(db, job)
    kinds = dict(db.execute(select(Page.number, Page.kind).where(Page.job_id == job.id)).all())
    blocks = dict(db.execute(select(Page.number, func.count(Segment.id)).join(Segment.page)
                             .where(Page.job_id == job.id).group_by(Page.number)).all())
    return [{"number": n, "kind": kinds.get(n) or "", "blocks": blocks.get(n, 0)} for n in range(1, count + 1)]


# ------------------------------------------------------------------ ejecuciones

class VariantIn(BaseModel):
    provider: str = Field(max_length=32)
    model: str | None = Field(default=None, max_length=64)
    thinking: str | None = Field(default=None, max_length=32)
    prompt: int | Annotated[str, Field(max_length=32)] | None = "production"
    prompt_name: str | None = Field(default=None, max_length=120)


class ScopeIn(BaseModel):
    job_id: int
    scope: Literal["page", "pages", "chapter", "book"] = "pages"  # pg.SCOPES
    pages: str = Field(default="", max_length=2000)
    variants: list[VariantIn]


class RunIn(ScopeIn):
    chapter: str | None = Field(default=None, max_length=512)
    confirm: bool = False  # obligatorio cuando la estimación pide confirmar (libro entero, muchos bloques)


def _result(res: dict) -> dict:
    d = {k: v for k, v in res.items() if k != "pdf"}  # la ruta del archivo no sale de la API
    d["composed"] = bool(res.get("pdf")) and Path(res["pdf"]).exists()
    return d


def _run(r: PlaygroundRun) -> dict:
    state = r.state or {}
    return {"id": r.id, "job_id": r.job_id, "task": r.task, "scope": r.scope or "pages", "pages": r.pages,
            "chapter": r.chapter, "variants": r.variants, "status": r.status, "progress": r.progress,
            "current_variant": r.current_variant, "blocks_done": state.get("done"), "blocks_total": state.get("total"),
            "stage": state.get("stage"), "composing": state.get("composing"),
            "trying": state.get("trying") or ({k: state["try"][k] for k in ("label", "page")} if state.get("try") else None),
            "results": [_result(x) for x in r.results or []], "votes": r.votes or {}, "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None, "book": None}


def _run_or_404(db: Session, run_id: int) -> PlaygroundRun:
    r = db.get(PlaygroundRun, run_id)
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return r


def _prepare(db: Session, body: ScopeIn) -> tuple[Job, str, list[int], list[dict], dict]:
    job = _job_done(db, body.job_id)
    task = pg.job_task(job)
    try:
        pages = pg.scope_pages(body.scope, body.pages, pg.book_pages(db, job))
        variants = pg.validate_variants([v.model_dump() for v in body.variants], task, pg.load_drafts(db))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return job, task, pages, variants, pg.estimate(db, job, task, body.scope, pages, variants)


@router.post("/playground/estimate")
def estimate(body: ScopeIn, db: Session = Depends(get_db)):
    return _prepare(db, body)[4]


@router.post("/playground/runs")
def create_run(body: RunIn, db: Session = Depends(get_db)):
    job, task, pages, variants, est = _prepare(db, body)
    if est["blocks"] == 0:
        raise HTTPException(400, "Esas páginas no tienen bloques para evaluar")
    if est["needs_confirm"] and not body.confirm:
        raise HTTPException(400, f"Son {est['blocks']} bloques (~{est['calls']} llamadas): confirma la evaluación.")
    names = {d.id: d.name for d in db.scalars(select(PromptDraft))}
    for v in variants:
        if isinstance(v["prompt"], int):
            v["prompt_name"] = names.get(v["prompt"], v["prompt_name"])
    r = PlaygroundRun(job_id=job.id, task=task, scope=body.scope, pages=pg.format_pages(pages), chapter=body.chapter,
                      variants=variants, results=[], status="queued", progress=0.0,
                      state={"done": 0, "total": est["blocks"]})
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


def _has_production(r: PlaygroundRun, job: Job) -> bool:
    return r.task == "translate" and bool(job.output_path) and Path(job.output_path).exists()


def _prod_entry(sg) -> dict:
    return {"output": sg.translation, "issues": list(sg.issues or []), "fit": sg.fit_scale}


def _plain_len(text: str | None) -> int:
    return len(TAG_RE.sub("", text or ""))


@router.get("/playground/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = _run_or_404(db, run_id)
    job = db.get(Job, r.job_id)
    pages = pg.parse_pages(r.pages, pg.book_pages(db, job) or 10**6)
    rows = pg.segment_rows(db, r.job_id, pages, r.task)
    d = _run(r)
    d["book"] = job.document.title_es or job.document.title or job.document.original_name
    d["page_list"] = pages
    d["production"] = _has_production(r, job)
    d["segments"] = [{"key": sg.seg_key, "page": n, "block_type": sg.block_type,
                      "source": sg.source_html or sg.source_text, "production": sg.translation}
                     for n, sg in rows]
    # resumen de toda la evaluación: bloques con avisos, páginas con avisos y páginas ganadas por columna
    votes = r.votes or {}
    summary = {}
    cols = [("prod", {sg.seg_key: _prod_entry(sg) for _, sg in rows})] if d["production"] else []
    cols += [(res["label"], res.get("segments") or {}) for res in r.results or []]
    for label, entries in cols:
        warn_pages = sorted({n for n, sg in rows if sg.seg_key in entries and pg.block_warnings(entries[sg.seg_key])})
        summary[label] = {
            "warn_blocks": sum(1 for _, sg in rows if sg.seg_key in entries and pg.block_warnings(entries[sg.seg_key])),
            "warn_pages": warn_pages, "won": sum(1 for v in votes.values() if v == label)}
    d["summary"] = summary
    return d


@router.get("/playground/runs/{run_id}/pages/{number}")
def run_page(run_id: int, number: int, db: Session = Depends(get_db)):
    """Una página de la mesa: sus bloques (con posición) y, por columna, la salida, los avisos y las métricas."""
    r = _run_or_404(db, run_id)
    job = db.get(Job, r.job_id)
    if number not in pg.parse_pages(r.pages, pg.book_pages(db, job) or 10**6):
        raise HTTPException(404, "Esa página no está en la evaluación")
    page = db.scalar(select(Page).where(Page.job_id == job.id, Page.number == number))
    rows = pg.segment_rows(db, job.id, [number], r.task)
    production = _has_production(r, job)
    cols: dict[str, dict] = {}
    if production:
        cols["prod"] = {"entries": {sg.seg_key: _prod_entry(sg) for _, sg in rows},
                        "review": list(page.review_reasons or []) if page and page.needs_review else [], "stale": False}
    for res in r.results or []:
        p = (res.get("pages") or {}).get(str(number)) or {}
        cols[res["label"]] = {"entries": res.get("segments") or {}, "review": p.get("reasons") or [],
                              "stale": number in (res.get("stale_pages") or [])}
    blocks, metrics = [], {}
    src_len = sum(_plain_len(sg.source_html or sg.source_text) for _, sg in rows) or 1
    for _, sg in rows:
        out = {}
        for label, c in cols.items():
            e = c["entries"].get(sg.seg_key)
            out[label] = {"output": (e or {}).get("output"), "warnings": pg.block_warnings(e),
                          "fit": (e or {}).get("fit")}
        blocks.append({"key": sg.seg_key, "bbox": list(sg.bbox), "block_type": sg.block_type,
                       "source": sg.source_html or sg.source_text, "cols": out})
    for label, c in cols.items():
        fits = [b["cols"][label]["fit"] for b in blocks if b["cols"][label]["fit"] is not None]
        metrics[label] = {
            "warn_blocks": sum(1 for b in blocks if b["cols"][label]["warnings"]),
            "min_scale": round(min(fits), 2) if fits else None,
            "length_pct": round(100 * (sum(_plain_len(b["cols"][label]["output"]) for b in blocks) / src_len - 1)),
            "review": c["review"], "stale": c["stale"]}
    return {"number": number, "width": page.width if page else None, "height": page.height if page else None,
            "blocks": blocks, "metrics": metrics, "vote": (r.votes or {}).get(str(number))}


@router.get("/playground/runs/{run_id}/pages/{number}/image")
def run_page_image(run_id: int, number: int, col: str = "orig", dpi: int = 110, db: Session = Depends(get_db)):
    """La página como imagen: original, producción o el PDF maquetado de una variante."""
    r = _run_or_404(db, run_id)
    job = db.get(Job, r.job_id)
    if col == "orig":
        path = job.document.path
    elif col == "prod":
        path = job.output_path if _has_production(r, job) else None
    else:
        res = next((x for x in r.results or [] if x.get("label") == col), None)
        if res is None:
            raise HTTPException(404, "Esa columna no existe")
        path = res.get("pdf")
    if not path or not Path(path).exists():
        raise HTTPException(409, "El PDF de esta columna todavía se está maquetando.")
    return _png(path, number, dpi)


def _png(path: str, index: int, dpi: int) -> Response:
    """Renderiza la página `index` (desde 1) de un PDF como PNG."""
    with pymupdf.open(path) as pdf:
        if not 1 <= index <= len(pdf):
            raise HTTPException(404, "Esa página no existe.")
        png = pdf[index - 1].get_pixmap(dpi=max(30, min(dpi, 200))).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


class VoteIn(BaseModel):
    vote: str | None = None  # etiqueta de la variante, "prod", "tie" o None para quitarlo


@router.put("/playground/runs/{run_id}/votes/{number}")
def vote(run_id: int, number: int, body: VoteIn, db: Session = Depends(get_db)):
    r = _run_or_404(db, run_id)
    job = db.get(Job, r.job_id)
    if number not in pg.parse_pages(r.pages, pg.book_pages(db, job) or 10**6):
        raise HTTPException(404, "Esa página no está en la evaluación")
    allowed = {v["label"] for v in r.variants} | {"tie", "prod"}
    if body.vote is not None and body.vote not in allowed:
        raise HTTPException(400, "Voto no válido")
    votes = dict(r.votes or {})
    if body.vote is None:
        votes.pop(str(number), None)
    else:
        votes[str(number)] = body.vote
    r.votes = votes
    db.commit()
    return {"votes": votes}


class TryIn(BaseModel):
    page: int
    variant: VariantIn


@router.post("/playground/runs/{run_id}/variants/{label}/try")
def try_variant(run_id: int, label: str, body: TryIn, db: Session = Depends(get_db)):
    """Vuelve a evaluar una sola página de una variante con otra configuración (método, modelo, prompt)."""
    r = _run_or_404(db, run_id)
    try:
        config = pg.validate_variants([body.variant.model_dump()], r.task, pg.load_drafts(db))[0]
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if isinstance(config["prompt"], int):
        d = db.get(PromptDraft, config["prompt"])
        config["prompt_name"] = d.name if d else config["prompt_name"]
    if r.status in ("queued", "running"):
        raise HTTPException(409, "La evaluación está en curso; espera a que termine.")
    try:
        pg.request_try(run_id, label, body.page, config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    db.expire_all()
    return _run(_run_or_404(db, run_id))


@router.post("/playground/runs/{run_id}/compose")
def compose_run(run_id: int, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    try:
        pg.request_compose(run_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    db.expire_all()
    return _run(_run_or_404(db, run_id))


@router.post("/playground/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    r = _run_or_404(db, run_id)
    if r.status in ("queued", "running", "paused"):
        r.status = "cancelled"
        db.commit()
    return _run(r)


@router.post("/playground/runs/{run_id}/resume")
def resume_run(run_id: int, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    try:
        pg.resume(run_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    db.expire_all()
    return _run(_run_or_404(db, run_id))


# ------------------------------------------------------------------ historial (agrupado por libro)

def _book_title(job: Job | None) -> str | None:
    return (job.document.title_es or job.document.title or job.document.original_name) if job else None


def _attempt(a: PlaygroundAttempt, detail: bool = False) -> dict:
    cfg = dict(a.config or {})
    if not detail:
        cfg.pop("prompt_text", None)
    return {"id": a.id, "run_id": a.run_id, "job_id": a.job_id, "label": a.label, "kind": a.kind, "pages": a.pages,
            "config": cfg, "seconds": a.seconds, "calls": a.calls, "tokens_in": a.tokens_in, "tokens_out": a.tokens_out,
            "tokens_cache_hit": a.tokens_cache_hit, "cost_usd": a.cost_usd, "error": a.error,
            "snapshot": bool(a.pdf) and Path(a.pdf).exists(), "blocks": len(a.segments or {}),
            "created_at": a.created_at.isoformat() if a.created_at else None}


def _attempt_or_404(db: Session, attempt_id: int) -> PlaygroundAttempt:
    a = db.get(PlaygroundAttempt, attempt_id)
    if not a:
        raise HTTPException(404, "Intento no encontrado")
    return a


@router.get("/playground/history")
def history_books(db: Session = Depends(get_db)):
    """Libros con pruebas en el playground: cuántas, tokens y costo estimado en total, y la fecha de la última."""
    A = PlaygroundAttempt
    rows = db.execute(select(A.job_id, func.count(A.id), func.sum(A.tokens_in), func.sum(A.tokens_out),
                             func.sum(A.cost_usd), func.max(A.created_at)).group_by(A.job_id)).all()
    jobs = {j.id: j for j in db.scalars(select(Job).where(Job.id.in_([r[0] for r in rows])))}
    out = [{"job_id": job_id, "book": _book_title(jobs.get(job_id)), "attempts": n, "tokens_in": tin or 0,
            "tokens_out": tout or 0, "cost_usd": round(cost or 0, 6), "last": last.isoformat() if last else None}
           for job_id, n, tin, tout, cost, last in rows]
    return sorted(out, key=lambda b: b["last"] or "", reverse=True)


@router.get("/playground/history/{job_id}")
def history_book(job_id: int, db: Session = Depends(get_db)):
    attempts = db.scalars(select(PlaygroundAttempt).where(PlaygroundAttempt.job_id == job_id)
                          .order_by(PlaygroundAttempt.id.desc())).all()
    votes = {r.id: r.votes or {} for r in db.scalars(select(PlaygroundRun).where(
        PlaygroundRun.id.in_({a.run_id for a in attempts})))}
    out = []
    for a in attempts:
        d = _attempt(a)
        rv = votes.get(a.run_id, {})
        d["won_pages"] = sorted(int(n) for n, v in rv.items() if v == a.label and n.isdigit())
        out.append(d)
    return {"job_id": job_id, "book": _book_title(db.get(Job, job_id)), "attempts": out}


@router.get("/playground/attempts/{attempt_id}")
def attempt_detail(attempt_id: int, db: Session = Depends(get_db)):
    """Configuración completa (con el prompt) y la salida de cada bloque junto a su original."""
    a = _attempt_or_404(db, attempt_id)
    run = db.get(PlaygroundRun, a.run_id)
    job = db.get(Job, a.job_id)
    pages = pg.parse_pages(a.pages, pg.book_pages(db, job) or 10**6) if job else []
    rows = pg.segment_rows(db, a.job_id, pages, run.task if run else "translate")
    entries = a.segments or {}
    d = _attempt(a, detail=True)
    d["book"] = _book_title(job)
    d["task"] = run.task if run else "translate"
    d["page_list"] = pages
    d["blocks"] = [{"key": sg.seg_key, "page": n, "block_type": sg.block_type, "source": sg.source_html or sg.source_text,
                    "output": (entries.get(sg.seg_key) or {}).get("output"),
                    "warnings": pg.block_warnings(entries.get(sg.seg_key))}
                   for n, sg in rows if sg.seg_key in entries]
    return d


@router.get("/playground/attempts/{attempt_id}/pages/{number}/image")
def attempt_page_image(attempt_id: int, number: int, dpi: int = 110, db: Session = Depends(get_db)):
    """La página tal como la dejó este intento (su copia); sin copia, el PDF actual de la variante."""
    a = _attempt_or_404(db, attempt_id)
    job = db.get(Job, a.job_id)
    pages = pg.parse_pages(a.pages, pg.book_pages(db, job) or 10**6) if job else []
    if number not in pages:
        raise HTTPException(404, "Esa página no está en este intento")
    if a.pdf and Path(a.pdf).exists():
        return _png(a.pdf, pages.index(number) + 1, dpi)
    run = db.get(PlaygroundRun, a.run_id)
    res = next((x for x in (run.results if run else None) or [] if x.get("label") == a.label), None)
    path = (res or {}).get("pdf")
    if not path or not Path(path).exists():
        raise HTTPException(409, "Este intento no tiene PDF maquetado.")
    return _png(path, number, dpi)
