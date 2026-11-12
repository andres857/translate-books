"""Playground de Administración: compara variantes (método, modelo, razonamiento y prompt) sobre un capítulo de
un libro ya procesado. Usa los segmentos guardados en la BD (sin volver a analizar el PDF), una caché en memoria
por variante (ni reutiliza ni contamina la de producción) y nunca cambia los prompts de producción."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import replace

from sqlalchemy import select, text

from app import runtime_settings
from app.db.models import GlossaryEntry, Job, Page, PlaygroundRun, PromptDraft, Segment
from app.db.session import SessionLocal
from app.pipeline.digitize import correct_segments
from app.pipeline.protect import Protector
from app.pipeline.runner import Cancelled
from app.pipeline.translate import DictCache, FatalAPIError, UsageMeter, translate_segments
from app.pipeline.types import Segment as Seg
from app.pipeline.types import Style

log = logging.getLogger(__name__)

MAX_VARIANTS = 4
MAX_PAGES = 40
MAX_SEGMENTS = 600
TASKS = ("translate", "correct")
PROVIDERS = ("claude", "deepseek", "fake")
CLAUDE_EFFORTS = ("", "low", "medium", "high")
LABELS = "ABCD"


def job_task(job: Job) -> str:
    return "correct" if (job.options or {}).get("mode") == "digitize" else "translate"


def parse_pages(spec: str, page_count: int) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", spec or "")
    if not m:
        raise ValueError("Páginas no válidas: usa un número o un rango como 12-18")
    a = int(m.group(1))
    b = int(m.group(2) or a)
    if a < 1 or b < a or b > page_count:
        raise ValueError(f"El rango debe estar entre 1 y {page_count}")
    if b - a + 1 > MAX_PAGES:
        raise ValueError(f"Máximo {MAX_PAGES} páginas por ejecución")
    return a, b


def validate_variants(raw: list[dict], task: str, drafts: dict[int, tuple[str, str]]) -> list[dict]:
    """Normaliza variantes. drafts: {id: (tarea, texto)}. El texto del borrador se copia en la variante."""
    if not raw:
        raise ValueError("Agrega al menos una variante")
    if len(raw) > MAX_VARIANTS:
        raise ValueError(f"Máximo {MAX_VARIANTS} variantes por ejecución")
    out = []
    for i, v in enumerate(raw):
        provider = v.get("provider")
        if provider not in PROVIDERS:
            raise ValueError("Método no válido")
        model = str(v.get("model") or "").strip()
        item = {"label": LABELS[i], "provider": provider, "model": "", "thinking": "", "effort": "",
                "prompt": "production", "prompt_name": "Producción", "prompt_text": None}
        if provider == "claude":
            model = model or "sonnet"
            if model not in runtime_settings.CLAUDE_MODELS:
                raise ValueError("Modelo de Claude no válido")
            effort = v.get("effort") or ""
            if effort not in CLAUDE_EFFORTS:
                raise ValueError("Esfuerzo de Claude no válido")
            item.update(model=model, effort=effort)
        elif provider == "deepseek":
            thinking = v.get("thinking") or "disabled"
            if thinking not in runtime_settings.THINKING_LEVELS:
                raise ValueError("Nivel de razonamiento no válido")
            item.update(model=model or "deepseek-flash", thinking=thinking)
        else:
            item["model"] = "fake"
        prompt = v.get("prompt", "production")
        if prompt not in (None, "", "production"):
            try:
                draft_task, draft_text = drafts[int(prompt)]
            except (KeyError, ValueError, TypeError):
                raise ValueError("El borrador de prompt no existe") from None
            if draft_task != task:
                raise ValueError("El borrador es de otra tarea")
            item.update(prompt=int(prompt), prompt_name=str(v.get("prompt_name") or f"Borrador {prompt}"),
                        prompt_text=draft_text)
        out.append(item)
    return out


def load_drafts(s) -> dict[int, tuple[str, str]]:
    return {d.id: (d.task, d.text) for d in s.scalars(select(PromptDraft))}


def segment_rows(s, job_id: int, a: int, b: int, task: str) -> list[tuple[int, Segment]]:
    rows = s.execute(select(Page.number, Segment).join(Segment.page)
                     .where(Page.job_id == job_id, Page.number >= a, Page.number <= b,
                            Segment.action == "translate")
                     .order_by(Page.number, Segment.id)).all()
    if task == "correct":  # como en digitize: solo bloques con letras
        rows = [r for r in rows if any(ch.isalpha() for ch in r[1].source_text or "")]
    return [(n, sg) for n, sg in rows]


def to_segments(rows: list[tuple[int, Segment]]) -> list[Seg]:
    segs = []
    for n, r in rows:
        segs.append(Seg(key=r.seg_key, page_no=n, bbox=tuple(r.bbox), line_rects=[], style=Style.from_dict(r.style or {}),
                        text=r.source_text or "", html=r.source_html or r.source_text or "",
                        block_type=r.block_type, action="translate", protected=r.protected_text,
                        placeholders=dict(r.placeholders or {})))
    return segs


class _Recorder:
    """Envuelve el traductor para guardar el último error de un lote (p. ej. JSON inválido por un prompt roto):
    translate_segments reintenta y no lo expone."""

    def __init__(self, inner):
        self.inner, self.last_error = inner, None

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def _wrap(self, fn, *args):
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            self.last_error = str(e)[:300] or type(e).__name__
            raise

    def translate_batch(self, items, context):
        return self._wrap(self.inner.translate_batch, items, context)

    def correct_batch(self, items, context):
        return self._wrap(self.inner.correct_batch, items, context)


def variant_translator(v: dict, task: str):
    base = runtime_settings.load()
    rs = replace(base, provider=v["provider"])
    if v["provider"] == "claude":
        rs.claude_model = v["model"]
    elif v["provider"] == "deepseek":
        rs.deepseek_model, rs.deepseek_thinking = v["model"], v["thinking"] or "disabled"
    prompts = {task: v["prompt_text"]} if v.get("prompt_text") else None
    translator = runtime_settings.make_translator(rs, prompts=prompts, effort=v.get("effort") or None)
    translator.meter = UsageMeter()
    return translator, rs.concurrency


def run_variant(v: dict, task: str, rows, ctx: dict, should_stop, on_progress) -> dict:
    from app.worker import friendly_error

    started = time.monotonic()
    result = {"label": v["label"], "segments": {}, "seconds": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0,
              "cost_usd": None, "cost_kind": "api_equivalent" if v["provider"] == "claude" else "unknown",
              "error": None, "fatal": None}
    rec = None
    try:
        translator, concurrency = variant_translator(v, task)
        rec = _Recorder(translator)
        segs = to_segments(rows)
        if task == "translate":
            translate_segments(segs, rec, DictCache(), Protector(), ctx["glossary"], ctx["title"],
                               concurrency, on_progress=on_progress, should_stop=should_stop, reprotect=False)
            outputs = {s.key: {"output": s.translation, "issues": list(s.issues)} for s in segs}
        else:
            correct_segments(segs, rec, DictCache(), ctx["lang"], concurrency, on_progress=on_progress,
                             should_stop=should_stop)
            outputs = {s.key: {"output": s.translation or getattr(s, "rejected_text", None), "issues": list(s.issues)}
                       for s in segs}
        result["segments"] = outputs
        if outputs and not any(o["output"] for o in outputs.values()):
            result["error"] = "Ningún bloque devolvió resultado" + (f": {rec.last_error}" if rec.last_error else "")
        result.update(translator.meter.snapshot())
    except Cancelled:
        raise
    except FatalAPIError as e:
        result["error"] = friendly_error(e)
        result["fatal"] = "quota" if "CLAUDE_QUOTA" in str(e) else "fatal"
    except Exception as e:  # noqa: BLE001
        log.exception("Playground: variante %s falló", v["label"])
        result["error"] = str(e)[:300] or type(e).__name__
    if rec is not None and hasattr(rec.inner, "meter") and rec.inner.meter is not None:
        result.update(rec.inner.meter.snapshot())
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


def execute(run_id: int) -> None:
    s = SessionLocal()
    last = [0.0, False]

    def should_stop() -> bool:
        now = time.time()
        if now - last[0] > 2:
            last[0] = now
            with SessionLocal() as s2:
                last[1] = s2.execute(select(PlaygroundRun.status).where(PlaygroundRun.id == run_id)).scalar() == "cancelled"
        return last[1]

    try:
        run = s.get(PlaygroundRun, run_id)
        job = s.get(Job, run.job_id)
        a, b = parse_pages(run.pages, job.document.page_count or 10**6)
        rows = segment_rows(s, job.id, a, b, run.task)
        doc = job.document
        ctx = {"title": doc.title or "", "lang": (job.options or {}).get("ocr_lang", "en"),
               "glossary": {g.source: g.target for g in s.scalars(select(GlossaryEntry).where(
                   (GlossaryEntry.document_id.is_(None)) | (GlossaryEntry.document_id == doc.id)))}}
        run.status, run.results, run.error = "running", [], None
        s.commit()
        n = len(run.variants)
        results = []
        for i, v in enumerate(run.variants):
            run.current_variant = i

            def tick(done, total, i=i):
                run.progress = round(100 * (i + (done / total if total else 1)) / n, 1)

            res = run_variant(v, run.task, rows, ctx, should_stop, tick)
            results.append(res)
            run.results = list(results)  # nueva lista: SQLAlchemy detecta el cambio del JSON
            run.progress = round(100 * (i + 1) / n, 1)
            s.commit()
            if res["fatal"] == "quota":
                raise FatalAPIError(res["error"])
            if should_stop():
                raise Cancelled()
        run.status, run.progress, run.current_variant = "done", 100.0, None
        s.commit()
    except Cancelled:
        s.rollback()
        log.info("Playground %s cancelado", run_id)
    except Exception as e:  # noqa: BLE001
        s.rollback()
        run = s.get(PlaygroundRun, run_id)
        if run.status != "cancelled":
            run.status = "failed"
            run.error = str(e)[:500] if isinstance(e, FatalAPIError) else "No se pudo ejecutar la evaluación."
            if not isinstance(e, FatalAPIError):
                log.exception("Playground %s falló", run_id)
            s.commit()
    finally:
        s.close()


def claim_run() -> int | None:
    with SessionLocal() as s:
        row = s.execute(text(
            "UPDATE playground_runs SET status='running' WHERE id = ("
            "SELECT id FROM playground_runs WHERE status='queued' ORDER BY id LIMIT 1) AND status='queued' RETURNING id"
        )).first()
        s.commit()
        return row[0] if row else None
