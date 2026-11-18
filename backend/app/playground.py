"""Playground de Administración: compara variantes (método, modelo, razonamiento y prompt) sobre una página, varias
páginas, un capítulo o el libro completo de un libro ya procesado. Usa los segmentos guardados en la BD (sin volver a analizar el PDF), una caché en memoria
por variante (ni reutiliza ni contamina la de producción) y nunca cambia los prompts de producción."""
from __future__ import annotations

import logging
import os
import re
import shutil
import statistics
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pymupdf
from sqlalchemy import delete, func, select, text, update

from app import runtime_settings
from app.config import get_settings
from app.db.models import (
    Document,
    GlossaryEntry,
    Job,
    Page,
    PlaygroundAttempt,
    PlaygroundRun,
    PromptDraft,
    ProtectedTerm,
    Segment,
)
from app.db.session import SessionLocal
from app.glossary_service import effective_glossary
from app.pipeline.digitize import correct_segments
from app.pipeline.protect import Protector
from app.pipeline.runner import Cancelled, PipelineOptions, run_pipeline
from app.pipeline.translate import DictCache, FakeTranslator, FatalAPIError, UsageMeter, _batches, translate_segments
from app.pipeline.types import Segment as Seg
from app.pipeline.types import Style

log = logging.getLogger(__name__)

MAX_VARIANTS = 4
MAX_PAGES = 80  # alcance «varias páginas»; capítulo y libro no tienen tope (se pide confirmación)
CONFIRM_BLOCKS = 600  # por encima, con variantes que consumen saldo, se pide confirmar
SCOPES = ("page", "pages", "chapter", "book")
TASKS = ("translate", "correct")
PROVIDERS = ("deepseek", "fake")
LABELS = "ABCD"
BATCH_CHARS = {"translate": 6000, "correct": 3000}  # los mismos lotes que producción
BATCH_ITEMS = 40
SAVE_EVERY = 5.0  # segundos entre guardados del progreso (para reanudar)
CHAPTER_RE = re.compile(r"^(chapter|cap[ií]tulo|part|parte|section|secci[oó]n|book|libro)\s+\w+", re.I)
NUMBERED_RE = re.compile(r"^\d{1,2}[.:]?\s+[^\W\d_]")


def job_task(job: Job) -> str:
    return "correct" if (job.options or {}).get("mode") == "digitize" else "translate"


def parse_pages(spec: str, page_count: int) -> list[int]:
    """«3, 7, 12-15» → [3, 7, 12, 13, 14, 15] (ordenadas y sin duplicados)."""
    pages: set[int] = set()
    for part in (spec or "").split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not m:
            raise ValueError("Páginas no válidas: usa números y rangos como 3, 7, 12-15")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if a < 1 or b < a or b > page_count:
            raise ValueError(f"Las páginas deben estar entre 1 y {page_count}")
        pages.update(range(a, b + 1))
    return sorted(pages)


def format_pages(pages: list[int]) -> str:
    """[3, 7, 12, 13, 14] → «3,7,12-14»."""
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}-{pages[j]}")
        i = j + 1
    return ",".join(out)


def scope_pages(scope: str, spec: str, page_count: int) -> list[int]:
    if scope not in SCOPES:
        raise ValueError("Alcance no válido")
    if scope == "book":
        return list(range(1, page_count + 1))
    pages = parse_pages(spec, page_count)
    if scope == "page" and len(pages) != 1:
        raise ValueError("Elige una sola página")
    if scope == "pages" and len(pages) > MAX_PAGES:
        raise ValueError(f"Máximo {MAX_PAGES} páginas sueltas; para más, usa un capítulo o el libro completo")
    return pages


def book_pages(s, job: Job) -> int:
    count = job.document.page_count
    if not count:
        count = s.scalar(select(func.max(Page.number)).where(Page.job_id == job.id)) or 0
    return count


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
        item = {"label": LABELS[i], "provider": provider, "model": "", "thinking": "",
                "prompt": "production", "prompt_name": "Producción", "prompt_text": None}
        if provider == "deepseek":
            thinking = v.get("thinking") or "disabled"
            if thinking not in runtime_settings.THINKING_LEVELS:
                raise ValueError("Nivel de razonamiento no válido")
            model = runtime_settings.normalize_model(model)
            if model not in runtime_settings.DEEPSEEK_MODELS:
                raise ValueError("Modelo no válido")
            item.update(model=model, thinking=thinking)
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


def segment_rows(s, job_id: int, pages: list[int], task: str) -> list[tuple[int, Segment]]:
    if not pages:
        return []
    contiguous = pages == list(range(pages[0], pages[-1] + 1))  # el libro entero: sin un IN enorme
    where = Page.number.between(pages[0], pages[-1]) if contiguous else Page.number.in_(pages)
    rows = s.execute(select(Page.number, Segment).join(Segment.page)
                     .where(Page.job_id == job_id, where, Segment.action == "translate")
                     .order_by(Page.number, Segment.id)).all()
    if task == "correct":  # como en digitize: solo bloques con letras
        rows = [r for r in rows if any(ch.isalpha() for ch in r[1].source_text or "")]
    return [(n, sg) for n, sg in rows]


def estimate(s, job: Job, task: str, scope: str, pages: list[int], variants: list[dict]) -> dict:
    """Páginas, bloques, caracteres y llamadas aproximadas; tiempo según evaluaciones anteriores del mismo modelo."""
    segs = to_segments(segment_rows(s, job.id, pages, task))
    for sg in segs:
        if task == "correct" or sg.protected is None:
            sg.protected = sg.html if task == "correct" else sg.text
    chars = sum(len(sg.protected or "") for sg in segs)
    calls = len(_batches(segs, BATCH_CHARS[task], BATCH_ITEMS))
    per_block = seconds_per_block(s)
    times = []
    for v in variants:
        rate = per_block.get((v["provider"], v["model"]))
        times.append({"label": v["label"], "seconds": round(rate * len(segs)) if rate is not None else None})
    known = [x["seconds"] for x in times]
    paid = any(v["provider"] != "fake" for v in variants)
    return {"scope": scope, "pages": len(pages), "page_spec": format_pages(pages), "blocks": len(segs),
            "chars": chars, "calls_per_variant": calls, "calls": calls * len(variants), "variants": times,
            "seconds": None if any(x is None for x in known) else sum(known),
            "paid": paid, "needs_confirm": paid and (scope == "book" or len(segs) > CONFIRM_BLOCKS)}


def seconds_per_block(s) -> dict[tuple[str, str], float]:
    """Segundos por bloque de cada método y modelo en las últimas evaluaciones terminadas."""
    acc: dict[tuple[str, str], list[float]] = {}
    runs = s.scalars(select(PlaygroundRun).where(PlaygroundRun.status == "done")
                     .order_by(PlaygroundRun.id.desc()).limit(100))
    for run in runs:
        for v, r in zip(run.variants or [], run.results or [], strict=False):
            n = len(r.get("segments") or {})
            if n and not r.get("error") and r.get("seconds"):
                tot = acc.setdefault((v["provider"], v["model"]), [0.0, 0])
                tot[0] += r["seconds"]
                tot[1] += n
    return {k: sec / n for k, (sec, n) in acc.items() if n}


def book_chapters(s, job: Job) -> list[dict]:
    """Capítulos del índice del PDF (marcadores, dos niveles) como rangos de páginas. Sin índice, se detectan por
    los títulos."""
    count = book_pages(s, job)
    try:
        with pymupdf.open(Path(job.document.path)) as doc:
            toc = [(lvl, title.strip(), page) for lvl, title, page, *_ in doc.get_toc(simple=False) if page >= 1]
    except Exception:  # noqa: BLE001
        toc = []
    toc = [t for t in toc if t[0] <= 2]
    if not toc:
        return detect_chapters(s, job)
    out = []
    for i, (lvl, title, start) in enumerate(toc):
        nxt = next((p for lv, _, p in toc[i + 1:] if lv <= lvl and p > start), count + 1)
        end = min(nxt - 1, count)
        out.append({"title": title or f"Sección {i + 1}", "level": lvl, "pages": f"{start}-{max(start, end)}",
                    "source": "toc"})
    return out


def _norm_title(text: str) -> str:
    return re.sub(r"[^\w]+", " ", re.sub(r"<[^>]+>", "", text or "").lower()).strip()


def translate_titles(s, job: Job, chapters: list[dict]) -> list[dict]:
    """Añade «title_es» a cada capítulo: la traducción del encabezado que lo abre (mismo texto que el título del
    índice, en su primera página o la siguiente). Sin coincidencia —o sin traducción— queda en None."""
    starts = {int(c["pages"].split("-")[0]) for c in chapters}
    near = starts | {n + 1 for n in starts}
    rows = s.execute(select(Page.number, Segment.source_text, Segment.translation).join(Segment.page)
                     .where(Page.job_id == job.id, Page.number.in_(near), Segment.translation.is_not(None))).all()
    by_page: dict[int, list[tuple[str, str]]] = {}
    for n, src, tr in rows:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tr or "")).strip()
        if text.endswith(".") and not text.endswith(".."):  # un título no lleva punto final
            text = text[:-1].rstrip()
        if text:
            by_page.setdefault(n, []).append((_norm_title(src), text))

    def find(title: str, start: int) -> str | None:
        want = _norm_title(title)
        if not want:
            return None
        for n in (start, start + 1):
            for src, tr in by_page.get(n, []):
                if src == want:
                    return tr
        for n in (start, start + 1):  # título del índice con añadidos («Aries 21 March–20 April» → «Aries»)
            for src, tr in by_page.get(n, []):
                if len(src) >= 3 and (want.startswith(src + " ") or src.startswith(want + " ")) and len(tr) <= 90:
                    return tr
        return None

    return [{**c, "title_es": find(c["title"], int(c["pages"].split("-")[0]))} for c in chapters]


def detect_chapters(s, job: Job) -> list[dict]:
    """Capítulos de un PDF sin índice: títulos grandes o «Chapter 3» al principio de la página, uno por página.
    Ignora las cabeceras repetidas en muchas páginas. Devuelve [] si no encuentra al menos dos."""
    rows = s.execute(select(Page.number, Page.height, Segment).join(Segment.page)
                     .where(Page.job_id == job.id).order_by(Page.number, Segment.id)).all()
    def sizes_of(kind: str) -> list[float]:
        return [x for x in (float((sg.style or {}).get("size") or 0) for _, _, sg in rows if sg.block_type == kind) if x > 0]

    # libros escaneados: el OCR marca todos los bloques como «ocr»; su talla mediana hace de cuerpo
    sizes = sizes_of("body") or sizes_of("ocr")
    if not sizes:
        return []
    body = statistics.median(sizes)
    titled = ("heading", "ocr")  # tipos que pueden ser título por tamaño o numeración
    page_h: dict[int, float] = {}
    for n, height, sg in rows:  # sin altura de página se usa el borde inferior del bloque más bajo
        page_h[n] = float(height) if height else max(page_h.get(n, 0.0), float(sg.bbox[3]) if sg.bbox else 0.0)

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    repeats = Counter(k for k in {(n, norm(sg.source_text)) for n, _, sg in rows})
    repeats = Counter(text for _, text in repeats.elements())
    found: dict[int, tuple[float, str]] = {}
    for n, _height, sg in rows:
        title = re.sub(r"\s+", " ", (sg.source_text or "").strip())
        if not title or len(title) > 90 or not any(ch.isalpha() for ch in title) or repeats[norm(title)] > 3:
            continue
        size = float((sg.style or {}).get("size") or 0)
        top = float(sg.bbox[1]) if sg.bbox else 0.0
        h = page_h.get(n) or 0.0
        near_top = bool(h) and top < h * 0.35
        big = sg.block_type in titled and size >= body * 1.4 and (sg.block_type == "heading" or near_top)
        named = near_top and (CHAPTER_RE.match(title) or (sg.block_type in titled and NUMBERED_RE.match(title)))
        if (big or named) and (n not in found or top < found[n][0]):
            found[n] = (top, title[:80])
    starts = sorted(found)
    if len(starts) < 2:
        return []
    count = book_pages(s, job)
    out = []
    if starts[0] > 1:
        out.append({"title": "Inicio", "level": 1, "pages": f"1-{starts[0] - 1}", "source": "detected"})
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else count
        out.append({"title": found[start][1], "level": 1, "pages": f"{start}-{max(start, end)}", "source": "detected"})
    return out


def to_segments(rows: list[tuple[int, Segment]]) -> list[Seg]:
    segs = []
    for n, r in rows:
        segs.append(Seg(key=r.seg_key, page_no=n, bbox=tuple(r.bbox), line_rects=[], style=Style.from_dict(r.style or {}),
                        text=r.source_text or "", html=r.source_html or r.source_text or "",
                        block_type=r.block_type, role=r.role, action="translate", protected=r.protected_text,
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
        except Exception as e:
            self.last_error = str(e)[:300] or type(e).__name__
            raise

    def translate_batch(self, items, context):
        return self._wrap(self.inner.translate_batch, items, context)

    def correct_batch(self, items, context):
        return self._wrap(self.inner.correct_batch, items, context)


def variant_translator(v: dict, task: str):
    base = runtime_settings.load()
    rs = replace(base, provider=v["provider"])
    if v["provider"] == "deepseek":
        rs.deepseek_model, rs.deepseek_thinking = v["model"], v["thinking"] or "disabled"
    prompts = {task: v["prompt_text"]} if v.get("prompt_text") else None
    translator = runtime_settings.make_translator(rs, prompts=prompts)
    translator.meter = UsageMeter()
    return translator, rs.concurrency


def is_out_of_balance(e: Exception) -> bool:
    """DeepSeek sin saldo (402): la evaluación se pausa y se reanuda tras recargar, sin repetir lo hecho."""
    return "402" in str(e) or "insufficient balance" in str(e).lower()


USAGE_KEYS = ("seconds", "calls", "tokens_in", "tokens_out", "tokens_cache_hit", "cost_usd")


def merge_usage(prev: dict | None, res: dict) -> None:
    """Suma al resultado el uso de los tramos anteriores a una pausa (tiempo, llamadas, tokens y costo)."""
    if not prev:
        return
    for k in ("seconds", "calls", "tokens_in", "tokens_out", "tokens_cache_hit"):
        res[k] = round((res.get(k) or 0) + (prev.get(k) or 0), 1) if k == "seconds" else (res.get(k) or 0) + (prev.get(k) or 0)
    if prev.get("calls"):
        res["cost_usd"] = (None if prev.get("cost_usd") is None or res.get("cost_usd") is None and res.get("calls")
                           else round((prev.get("cost_usd") or 0) + (res.get("cost_usd") or 0), 8))


def run_variant(v: dict, task: str, rows, ctx: dict, should_stop, on_progress, cache: DictCache | None = None) -> dict:
    """cache: salidas ya obtenidas por esta variante (al reanudar no se vuelven a pedir)."""
    from app.worker import friendly_error

    cache = cache if cache is not None else DictCache()
    started = time.monotonic()
    result = {"label": v["label"], "segments": {}, "seconds": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0,
              "tokens_cache_hit": 0, "cost_usd": 0.0 if v["provider"] == "fake" else None, "cost_kind": "estimate",
              "error": None, "fatal": None}
    rec = None
    try:
        translator, concurrency = variant_translator(v, task)
        rec = _Recorder(translator)
        segs = to_segments(rows)
        if task == "translate":
            translate_segments(segs, rec, cache, Protector(), ctx["glossary"], ctx["title"], concurrency,
                               max_chars=BATCH_CHARS[task], max_items=BATCH_ITEMS, on_progress=on_progress,
                               should_stop=should_stop, reprotect=False, domain=ctx.get("domain", ""))
            outputs = {s.key: {"output": s.translation, "issues": list(s.issues)} for s in segs}
        else:
            correct_segments(segs, rec, cache, ctx["lang"], concurrency, max_chars=BATCH_CHARS[task],
                             max_items=BATCH_ITEMS, on_progress=on_progress, should_stop=should_stop)
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
        result["fatal"] = "balance" if is_out_of_balance(e) else "fatal"
    except Exception as e:
        log.exception("Playground: variante %s falló", v["label"])
        result["error"] = str(e)[:300] or type(e).__name__
    if rec is not None and hasattr(rec.inner, "meter") and rec.inner.meter is not None:
        result.update(rec.inner.meter.snapshot())
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


# ------------------------------------------------------------------ PDF por variante

WARN_SCALE = 0.8  # por debajo, el texto se redujo tanto que se avisa (como en producción)
CFG_KEYS = ("provider", "model", "thinking", "prompt", "prompt_text")


def run_dir(run_id: int) -> Path:
    return get_settings().outputs_dir / "playground" / f"run_{run_id}"


def block_warnings(entry: dict | None) -> list[str]:
    """Avisos de un bloque: los de la traducción, los de la maquetación y la escala si el texto no cupo."""
    if not entry:
        return []
    out = list(entry.get("issues") or []) + [x for x in entry.get("layout_issues") or [] if x not in (entry.get("issues") or [])]
    fit = entry.get("fit")
    if fit is not None and fit < WARN_SCALE:
        out.append(f"escala {fit:.2f}: el texto no cabe en su caja".replace(".", ","))
    if not entry.get("output"):
        out.append("sin resultado")
    return out


def production_overrides(s, job_id: int, pages: list[int]) -> dict[str, str]:
    rows = s.execute(select(Segment.seg_key, Segment.translation).join(Segment.page).where(
        Page.job_id == job_id, Page.number.in_(pages), Segment.action == "translate",
        Segment.translation.isnot(None))).all()
    return {k: t for k, t in rows if t}


def _splice(target: Path, new_pdf: Path, pages: list[int]) -> None:
    """Sustituye esas páginas del PDF de la variante por las recién compuestas (como recompose_page)."""
    tmp = target.with_name(target.name + ".tmp")
    with pymupdf.open(target) as out, pymupdf.open(new_pdf) as new:
        if len(new) != len(out):
            raise ValueError("El PDF compuesto no tiene las mismas páginas")
        for n in pages:
            out.insert_pdf(new, from_page=n - 1, to_page=n - 1, start_at=n - 1)
            out.delete_page(n)
        out.save(tmp, garbage=1, deflate=True)
    os.replace(tmp, target)


def compose_variant(s, job: Job, outputs: dict[str, dict], pages: list[int], target: Path,
                    splice: bool = False, should_stop=None) -> dict:
    """Maqueta las páginas evaluadas con las salidas de una variante, con el mismo motor que producción.
    No llama a ninguna API: los bloques que la variante no tradujo llevan la traducción de producción y
    las salidas de la variante no se acortan (que no quepan es parte de lo que se evalúa).
    Devuelve {"pages": {n: {needs_review, reasons}}, "blocks": {clave: {fit, issues}}}."""
    st = get_settings()
    # base: el texto original (libro solo preparado o bloque sin traducir); encima producción y la variante
    overrides = {sg.seg_key: sg.source_html or sg.source_text for _, sg in segment_rows(s, job.id, pages, "translate")}
    overrides.update(production_overrides(s, job.id, pages))
    overrides.update({k: o["output"] for k, o in outputs.items() if o.get("output")})
    opts = PipelineOptions(min_font_scale=st.min_font_scale, min_font_size_pt=st.min_font_size_pt, concurrency=1,
                           fonts_dirs=st.fonts_dirs, only_pages=set(pages), detect_names=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = target.parent / f"_tmp_{target.stem}"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    try:
        result = run_pipeline(Path(job.document.path), tmp_dir, FakeTranslator(), DictCache(), {}, {}, opts,
                              should_stop=should_stop, overrides=overrides)
        if splice and target.exists():
            _splice(target, result.output_pdf, pages)
        else:
            os.replace(result.output_pdf, target)
        wanted = set(pages)
        info = {"pages": {}, "blocks": {}}
        for p in result.pages:
            if p.number in wanted:
                info["pages"][str(p.number)] = {"needs_review": p.needs_review, "reasons": list(p.review_reasons)}
                for sg in p.segments:
                    info["blocks"][sg.key] = {"fit": sg.fit_scale, "issues": list(sg.issues or [])}
        return info
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def compose_result(s, run: PlaygroundRun, job: Job, res: dict, pages: list[int], only: list[int] | None = None,
                   should_stop=None) -> dict:
    """Devuelve una copia del resultado con su PDF compuesto (o el motivo si no se pudo). La traducción
    evaluada no se pierde si falla la maquetación."""
    r = dict(res)
    if run.task != "translate" or not r.get("segments"):
        return r
    target = run_dir(run.id) / f"{r['label']}.pdf"
    splice = bool(only) and target.exists()
    try:
        info = compose_variant(s, job, r["segments"], only if splice else pages, target, splice, should_stop)
    except Cancelled:
        raise
    except Exception:
        log.exception("Playground %s: no se pudo componer la variante %s", run.id, r["label"])
        r["compose_error"] = "No se pudo maquetar el PDF de esta variante; el texto sí está evaluado."
        return r
    segs = {}
    for k, o in r["segments"].items():
        b = info["blocks"].get(k)
        segs[k] = {**o, "fit": b["fit"], "layout_issues": b["issues"]} if b else o
    r["segments"] = segs
    r["pages"] = {**(r.get("pages") or {}), **info["pages"]} if splice else info["pages"]
    r["pdf"], r["composed_at"] = str(target), int(time.time())
    r.pop("compose_error", None)
    return r


ATTEMPT_CFG = ("provider", "model", "thinking", "prompt", "prompt_name", "prompt_text")


def delete_job(s, job: Job) -> list[Path]:
    """Borra de la BD el análisis de un libro (sin commit): evaluaciones e intentos, páginas y bloques (en cascada)
    y el trabajo; y el documento si no le queda otro análisis. Devuelve las rutas en disco que hay que borrar."""
    paths: list[Path] = [get_settings().outputs_dir / f"job_{job.id}"]
    paths += [Path(p) for p in (job.output_path, job.report_path) if p]
    # en bloque (#20): solo se leen las columnas con rutas; intentos y evaluaciones antes del trabajo (RESTRICT)
    paths += [run_dir(rid) for rid in s.scalars(select(PlaygroundRun.id).where(PlaygroundRun.job_id == job.id))]
    paths += [Path(p) for p in s.scalars(select(PlaygroundAttempt.pdf).where(
        PlaygroundAttempt.job_id == job.id, PlaygroundAttempt.pdf.is_not(None))) if p]
    s.execute(delete(PlaygroundAttempt).where(PlaygroundAttempt.job_id == job.id))
    s.execute(delete(PlaygroundRun).where(PlaygroundRun.job_id == job.id))
    doc = job.document
    s.delete(job)  # páginas y bloques caen en cascada
    s.flush()
    if doc is not None and not s.scalar(select(func.count(Job.id)).where(Job.document_id == doc.id)):
        for model in (GlossaryEntry, ProtectedTerm):
            s.execute(delete(model).where(model.document_id == doc.id))
        shared = s.scalar(select(func.count(Document.id)).where(Document.sha256 == doc.sha256, Document.id != doc.id))
        if not shared and doc.path:
            paths.append(Path(doc.path).parent)  # carpeta uploads/<sha>
        s.delete(doc)
    return paths


def remove_path(path: Path) -> None:
    """Borra un archivo o carpeta de salida; solo dentro de las carpetas de datos de la app."""
    st = get_settings()
    roots = [Path(st.outputs_dir).resolve(), Path(st.uploads_dir).resolve()]
    try:
        p = path.resolve()
        if not any(p != r and p.is_relative_to(r) for r in roots):
            log.warning("No se borra %s: está fuera de las carpetas de datos", p)
            return
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    except OSError:
        log.warning("No se pudo borrar %s", path, exc_info=True)


def attempts_dir(run_id: int) -> Path:
    return run_dir(run_id) / "attempts"


def snapshot_pages(src: str | None, dest: Path, pages: list[int]) -> bool:
    """Copia esas páginas del PDF de la variante (en orden) para que pruebas posteriores no las pisen."""
    if not src or not Path(src).exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(src) as pdf, pymupdf.open() as out:
        for n in pages:
            if 1 <= n <= len(pdf):
                out.insert_pdf(pdf, from_page=n - 1, to_page=n - 1)
        if not len(out):
            return False
        out.save(dest, garbage=1, deflate=True)
    return True


def record_attempt(s, run: PlaygroundRun, v: dict, res: dict, pages: list[int], kind: str) -> PlaygroundAttempt | None:
    """Guarda en el historial una variante evaluada o una prueba de página. Un fallo aquí no rompe la evaluación."""
    try:
        cost = 0.0 if v.get("provider") == "fake" else res.get("cost_usd")
        a = PlaygroundAttempt(run_id=run.id, job_id=run.job_id, label=v["label"], kind=kind, pages=format_pages(pages),
                              config={k: v.get(k) for k in ATTEMPT_CFG}, segments=res.get("segments") or {},
                              seconds=res.get("seconds") or 0.0, calls=res.get("calls") or 0,
                              tokens_in=res.get("tokens_in") or 0, tokens_out=res.get("tokens_out") or 0,
                              tokens_cache_hit=res.get("tokens_cache_hit") or 0, cost_usd=cost, error=res.get("error"))
        s.add(a)
        s.flush()
        dest = attempts_dir(run.id) / f"{a.id}.pdf"
        if run.task == "translate" and snapshot_pages(res.get("pdf"), dest, pages):
            a.pdf = str(dest)
        s.commit()
        return a
    except Exception:
        log.exception("Playground %s: no se pudo guardar el intento de %s", run.id, v.get("label"))
        s.rollback()
        return None


def _cfg(v: dict) -> tuple:
    return tuple(v.get(k) for k in CFG_KEYS)


def execute(run_id: int) -> None:
    """Ejecuta (o continúa) una evaluación. Las variantes ya terminadas no se repiten y la que quedó a medias
    reutiliza lo guardado en run.state. Sin saldo, la evaluación queda en pausa, no en error. Cada variante
    terminada se maqueta en su propio PDF para compararlo con el original página a página."""
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
        pages = parse_pages(run.pages, book_pages(s, job) or 10**6)
        doc = job.document
        ctx = {"title": doc.title or "", "lang": (job.options or {}).get("ocr_lang", "en"),
               "glossary": effective_glossary(s, doc.id)[0], "domain": doc.domain or ""}
        state = dict(run.state or {})
        caches = dict(state.get("caches") or {})
        usage = dict(state.get("usage") or {})
        results = list(run.results or [])
        if not _set_if_running(s, run_id, ("queued", "running"), status="running", error=None):
            return  # cancelada entre claim_run y aquí: no se vuelve a poner en curso
        n = len(run.variants)

        def save(commit: bool = True) -> None:
            run.state = {**state, "caches": dict(caches), "usage": dict(usage)}  # nuevo dict: se detecta el cambio
            if commit:
                s.commit()

        def compose(i: int, only: list[int] | None = None) -> None:
            state["stage"], state["composing"] = "compose", results[i]["label"]
            save()
            results[i] = compose_result(s, run, job, results[i], pages, only, should_stop)
            run.results = list(results)
            state.pop("composing", None)
            state["stage"] = "translate"
            save()

        if state.get("try"):
            try_page(s, run, job, state, results, pages, ctx, should_stop, save, compose)
            return

        rows = segment_rows(s, job.id, pages, run.task)
        state["stage"] = "translate"
        for i in range(len(results), n):
            v = run.variants[i]
            label = v["label"]
            run.current_variant = i
            cache = DictCache()
            cache.data = dict(caches.get(label) or {})
            saved = [time.monotonic()]

            def tick(done, total, i=i, cache=cache, label=label):
                run.progress = round(100 * (i + (done / total if total else 1)) / n, 1)
                state["done"], state["total"] = done, total
                # B023 falso positivo: run_variant llama a tick() dentro de esta iteración, nunca después
                if time.monotonic() - saved[0] >= SAVE_EVERY:  # noqa: B023
                    caches[label] = dict(cache.data)
                    save()
                    saved[0] = time.monotonic()  # noqa: B023

            res = run_variant(v, run.task, rows, ctx, should_stop, tick, cache)
            if res["fatal"] == "balance":
                caches[label] = dict(cache.data)
                prev = usage.get(label)
                merge_usage(prev, res)
                usage[label] = {k: res.get(k) for k in USAGE_KEYS}
                save(commit=False)
                _set_if_running(s, run_id, status="paused",
                           error=f"{res['error']} Lo ya evaluado se conserva: recarga saldo y pulsa «Reanudar».")
                return
            merge_usage(usage.pop(label, None), res)
            caches.pop(label, None)
            results.append(res)
            run.results = list(results)  # nueva lista: SQLAlchemy detecta el cambio del JSON
            save()
            compose(len(results) - 1)
            record_attempt(s, run, v, results[-1], pages, "run")
            run.progress = round(100 * (i + 1) / n, 1)
            save()
            if should_stop():
                raise Cancelled()
        # evaluaciones antiguas o interrumpidas: maquetar lo que aún no tiene PDF (sin volver a traducir)
        for i, r in enumerate(results):
            if run.task == "translate" and r.get("segments") and not r.get("pdf") and not r.get("compose_error"):
                compose(i)
        run.state = {"done": state.get("total"), "total": state.get("total")}  # las salidas ya están en results
        _set_if_running(s, run_id, status="done", progress=100.0, current_variant=None)
    except Cancelled:
        s.rollback()
        log.info("Playground %s cancelado", run_id)
    except Exception as e:
        s.rollback()
        if not isinstance(e, FatalAPIError):
            log.exception("Playground %s falló", run_id)
        _set_if_running(s, run_id, status="failed",
                   error=str(e)[:500] if isinstance(e, FatalAPIError) else "No se pudo ejecutar la evaluación.")
    finally:
        s.close()


def _set_if_running(s, run_id: int, allowed: tuple[str, ...] = ("running",), **values) -> bool:
    """Actualiza la evaluación solo si sigue en curso: la API pudo cancelarla después de la última consulta
    de should_stop. Si ya no lo está, descarta lo pendiente de la sesión y no toca nada más."""
    if s.execute(update(PlaygroundRun).where(PlaygroundRun.id == run_id, PlaygroundRun.status.in_(allowed))
                 .values(**values)).rowcount:
        s.commit()
        return True
    s.rollback()
    log.info("Playground %s: ya no está en curso (cancelado); no se marca como %s", run_id, values.get("status"))
    return False


def try_page(s, run: PlaygroundRun, job: Job, state: dict, results: list, pages: list[int], ctx: dict,
             should_stop, save, compose) -> None:
    """«Probar en la pág. N»: vuelve a evaluar una sola página de una variante con su configuración nueva y
    recompone solo esa página. Si la configuración cambió, el resto de páginas queda «con la anterior»."""
    t = state["try"]
    label, page = t["label"], int(t["page"])
    i = next(k for k, v in enumerate(run.variants) if v["label"] == label)
    v = {**t["config"], "label": label}
    rows = segment_rows(s, job.id, [page], run.task)
    run.current_variant = i
    state.update(stage="translate", done=0, total=len(rows), trying={"label": label, "page": page})
    save()

    def tick(done, total):
        state["done"], state["total"] = done, total
        run.progress = round(100 * done / total, 1) if total else 100.0

    res = run_variant(v, run.task, rows, ctx, should_stop, tick)

    def finish(error: str | None = None) -> None:
        for k in ("try", "trying", "stage", "composing"):
            state.pop(k, None)
        save(commit=False)
        _set_if_running(s, run.id, status="done", progress=100.0, current_variant=None, error=error)

    if res["error"] and not any(o.get("output") for o in res["segments"].values()):
        finish(f"La prueba de la variante {label} en la página {page} no se pudo hacer: {res['error']}")
        return
    r = dict(results[i])
    own = {k: res.get(k) for k in USAGE_KEYS}  # uso de esta prueba sola, para el historial
    merge_usage({k: r.get(k) for k in USAGE_KEYS}, res)
    r.update({k: res.get(k) for k in USAGE_KEYS})
    r["segments"] = {**(r.get("segments") or {}), **res["segments"]}
    stale = set(pages) if _cfg(run.variants[i]) != _cfg(v) else set(r.get("stale_pages") or [])
    stale.discard(page)
    r["stale_pages"] = sorted(stale)
    variants = [dict(x) for x in run.variants]
    variants[i] = v
    run.variants = variants
    results[i] = r
    run.results = list(results)
    save()
    compose(i, only=[page])
    composed = results[i]
    record_attempt(s, run, v, {**own, "error": res["error"], "pdf": composed.get("pdf"),
                               "segments": {k: (composed.get("segments") or {}).get(k, o) for k, o in res["segments"].items()}},
                   [page], "try")
    finish(f"Variante {label}, página {page}: {res['error']}" if res["error"] else None)


def request_try(run_id: int, label: str, page: int, config: dict) -> None:
    with SessionLocal() as s:
        run = s.get(PlaygroundRun, run_id)
        if run.status != "done":
            raise ValueError("Espera a que termine la evaluación para probar una página")
        if label not in {v["label"] for v in run.variants} or len(run.results or []) != len(run.variants):
            raise ValueError("Esa variante no está en la evaluación")
        job = s.get(Job, run.job_id)
        if page not in parse_pages(run.pages, book_pages(s, job) or 10**6):
            raise ValueError("Esa página no está en la evaluación")
        run.state = {**(run.state or {}), "try": {"label": label, "page": page, "config": config}}
        run.status, run.error, run.progress = "queued", None, 0.0
        s.commit()


def request_compose(run_id: int) -> None:
    """Evaluaciones anteriores a la mesa de PDF (o con la maquetación fallida): maquetar sin volver a traducir."""
    with SessionLocal() as s:
        run = s.get(PlaygroundRun, run_id)
        if run.status != "done" or run.task != "translate":
            raise ValueError("Solo se maquetan evaluaciones de traducción terminadas")
        results = []
        for r in run.results or []:
            r = dict(r)
            r.pop("compose_error", None)
            if r.get("pdf") and not Path(r["pdf"]).exists():
                r.pop("pdf")
            results.append(r)
        run.results = results
        run.status, run.error = "queued", None
        s.commit()


def resume(run_id: int) -> None:
    """Vuelve a poner en cola una evaluación pausada por falta de saldo; continúa donde quedó."""
    with SessionLocal() as s:
        run = s.get(PlaygroundRun, run_id)
        if run is None or run.status != "paused":
            raise ValueError("Solo se puede reanudar una evaluación en pausa")
        run.status, run.error = "queued", None
        s.commit()


def claim_run() -> int | None:
    with SessionLocal() as s:
        row = s.execute(text(
            "UPDATE playground_runs SET status='running' WHERE id = ("
            "SELECT id FROM playground_runs WHERE status='queued' ORDER BY id LIMIT 1) AND status='queued' RETURNING id"
        )).first()
        s.commit()
        return row[0] if row else None
