"""Worker local: toma trabajos de la cola (tabla jobs en SQLite) y ejecuta el pipeline.

python -m app.worker
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy import select, text, update

from app import playground, runtime_settings
from app.config import get_settings
from app.db.cache import SqlCache
from app.db.models import Document, Job, Page, ProtectedTerm, Segment
from app.db.session import SessionLocal
from app.glossary_service import effective_glossary, save_auto
from app.pipeline.digitize import DigitizeOptions, run_digitize
from app.pipeline.epub import build_epub_for_job
from app.pipeline.protect import Protector
from app.pipeline.runner import (
    Cancelled,
    PipelineOptions,
    discover_book_glossary,
    prepare_book,
    recompose_page,
    run_pipeline,
)
from app.pipeline.translate import FatalAPIError
from app.pipeline.types import ensure_unique_keys

log = logging.getLogger("worker")

# peso de cada etapa en el progreso global (%)
STAGE_WEIGHTS = {"analyze": (0, 4), "ocr": (4, 10), "protect": (10, 12), "glossary": (12, 16), "translate": (16, 78),
                 "rebuild": (78, 93), "validate": (93, 100)}
# modo digitalizar (OCR sin traducir); sin corrección con el modelo, la etapa "correct" no aparece
# modo preparar (Playground): solo análisis, OCR y protección; sin traducir ni maquetar
PREPARE_WEIGHTS = {"analyze": (0, 35), "ocr": (35, 85), "protect": (85, 88), "glossary": (88, 100)}
DIGITIZE_WEIGHTS = {"analyze": (0, 2), "ocr": (2, 60), "correct": (60, 85), "compose": (85, 98),
                    "validate": (98, 100)}


def friendly_error(e: Exception) -> str:
    msg = str(e)
    if isinstance(e, FatalAPIError):
        if "DEEPSEEK_API_KEY" in msg:
            return "Falta la llave de DeepSeek. Agrégala en Administración › Configuración."
        if "401" in msg:
            return "La llave de DeepSeek no es válida. Revisa la configuración."
        if "402" in msg:
            return "La cuenta de DeepSeek no tiene saldo suficiente."
        return "El servicio de traducción rechazó la solicitud. Revisa la configuración."
    if "OCR_MISSING" in msg:
        return "Falta OCRmyPDF/Tesseract en el equipo del servidor; no se puede digitalizar."
    if "OCRmyPDF falló" in msg:
        return "El OCR no pudo procesar este PDF. Revisa que no esté dañado e inténtalo de nuevo."
    if "contraseña" in msg:
        return msg
    return "Ocurrió un error inesperado al procesar el libro. Puedes intentar reanudar el proceso."


def claim_job() -> int | None:
    with SessionLocal() as s:
        row = s.execute(text(
            "UPDATE jobs SET status='running', error=NULL WHERE id = ("
            "SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1) AND status='queued' RETURNING id"
        )).first()
        s.commit()
        return row[0] if row else None


def close_job(s, job_id: int, **values) -> bool:
    """Cierra un trabajo solo si sigue 'running': la API pudo cancelarlo (o reanudarlo) después de la última
    consulta de should_stop. Si ya no está en curso, descarta lo pendiente de la sesión y no toca nada más."""
    if s.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(**values)).rowcount:
        s.commit()
        return True
    s.rollback()
    log.info("Trabajo %s: ya no está en curso (cancelado); no se cierra como %s", job_id, values.get("status"))
    return False


def save_results(s, job: Job, pages, only: set[int] | None = None) -> None:
    """Guarda páginas y segmentos. only: sustituir solo esas páginas (recomposición)."""
    old = select(Page).where(Page.job_id == job.id)
    if only is not None:
        old = old.where(Page.number.in_(only))
    for row in s.scalars(old).all():  # por el ORM, para que se borren también sus segmentos
        s.delete(row)
    s.flush()
    for info in pages:
        if only is not None and info.number not in only:
            continue
        ensure_unique_keys(info)  # red de seguridad: un id repetido haría que una traducción pise a otra
        page = Page(job_id=job.id, number=info.number, width=info.width, height=info.height,
                    rotation=info.rotation, kind=info.kind, image_count=info.image_count,
                    drawing_count=info.drawing_count, status="done", needs_review=info.needs_review,
                    review_reasons=info.review_reasons)
        page.segments = [Segment(seg_key=sg.key, bbox=list(sg.bbox), block_type=sg.block_type, role=sg.role,
                                 style=sg.style.to_dict(), source_text=sg.text, source_html=sg.html,
                                 protected_text=sg.protected, placeholders=sg.placeholders,
                                 translation=sg.translation, action=sg.action, status="done",
                                 fit_scale=sg.fit_scale, issues=sg.issues, ocr_confidence=sg.ocr_confidence,
                                 edited=sg.edited)
                         for sg in info.segments]
        s.add(page)


def process(job_id: int) -> None:
    st = get_settings()
    s = SessionLocal()
    job = s.get(Job, job_id)
    doc: Document = job.document
    last_commit = [0.0]
    last_check = [0.0, False]

    def should_stop() -> bool:
        now = time.time()
        if now - last_check[0] > 2:
            last_check[0] = now
            with SessionLocal() as s2:
                status = s2.execute(select(Job.status).where(Job.id == job_id)).scalar()
            last_check[1] = status in ("cancelled", "paused")
        return last_check[1]

    options = dict(job.options or {})
    digitize = options.get("mode") == "digitize"
    prepare = options.get("mode") == "prepare"
    weights = DIGITIZE_WEIGHTS if digitize else PREPARE_WEIGHTS if prepare else STAGE_WEIGHTS

    def progress(stage: str, done: int, total: int, page: int | None) -> None:
        a, b = weights.get(stage, (0, 100))
        job.stage = stage
        job.progress = round(a + (b - a) * (done / total if total else 1), 1)
        if page:
            job.current_page = page
        now = time.time()
        if now - last_commit[0] > 1 or done == total:
            last_commit[0] = now
            s.commit()

    try:
        rs = runtime_settings.load()  # se lee en cada trabajo: cambiar el modo en Ajustes no exige reiniciar
        if digitize:
            process_digitize(s, job, rs, options, progress, should_stop)
            return
        terms = {t.term: t.category for t in s.scalars(select(ProtectedTerm).where(
            (ProtectedTerm.document_id.is_(None)) | (ProtectedTerm.document_id == doc.id)))}
        glossary, has_auto = effective_glossary(s, doc.id)
        opts = PipelineOptions(min_font_scale=st.min_font_scale, min_font_size_pt=st.min_font_size_pt,
                               concurrency=rs.concurrency, batch_chars=st.translation_batch_chars,
                               batch_items=st.translation_batch_max_segments, fonts_dirs=st.fonts_dirs,
                               detect_names=rs.provider != "fake",
                               # el glosario se descubre una vez por libro; después se revisa en Términos
                               discover_glossary=rs.provider != "fake" and not has_auto, domain=doc.domain or "")
        if prepare:  # no traduce: el modelo solo se usa (si hay llave) para generar el glosario del libro
            process_prepare(s, job, rs, terms, opts, progress, should_stop)
            return
        translator = runtime_settings.make_translator(rs)
        if options.get("recompose"):
            process_recompose(s, job, options, translator, terms, glossary, opts, progress, should_stop)
            return
        log.info("Trabajo %s: modo de traducción %s (%s)", job_id, rs.provider, translator.model)
        out_dir = st.outputs_dir / f"job_{job.id}"
        with SessionLocal() as cache_s:
            result = run_pipeline(Path(doc.path), out_dir, translator, SqlCache(cache_s), terms, glossary,
                                  opts, progress, should_stop)
        save_results(s, job, result.pages)
        if opts.discover_glossary:  # solo si se descubrió en esta pasada (si no, se borraría el revisado)
            save_auto(s, doc, result.domain, result.glossary_auto)
        doc.title, doc.title_es = result.title, result.title_es
        job.output_path, job.report_path = str(result.output_pdf), str(result.report_path)
        if not close_job(s, job.id, status="done", stage="done", progress=100.0):
            return
        log.info("Trabajo %s terminado: %s", job.id, result.output_pdf)
        try:  # EPUB para Kindle; si falla, el PDF sigue disponible y el EPUB se genera al descargarlo
            log.info("EPUB listo: %s", build_epub_for_job(s, job))
        except Exception:  # noqa: BLE001
            log.exception("No se pudo generar el EPUB del trabajo %s", job.id)
    except Cancelled:
        s.rollback()
        job = s.get(Job, job_id)
        log.info("Trabajo %s detenido (%s)", job_id, job.status)
    except Exception as e:  # noqa: BLE001
        log.exception("Trabajo %s falló", job_id)
        s.rollback()
        close_job(s, job_id, status="failed", error=friendly_error(e))
    finally:
        s.close()


def process_recompose(s, job: Job, options: dict, translator, terms, glossary, opts, progress, should_stop) -> None:
    """Recompone las páginas pedidas desde el admin con las traducciones corregidas a mano. Si falla, el
    libro ya traducido sigue disponible: el trabajo vuelve a 'done' y el motivo queda en las opciones."""
    numbers = [int(n) for n in options.get("recompose") or []]
    try:
        if not job.output_path or not Path(job.output_path).exists():
            raise FileNotFoundError("No existe el PDF traducido")
        for n in numbers:
            overrides = {sg.seg_key: sg.translation for sg in s.scalars(
                select(Segment).join(Page).where(Page.job_id == job.id, Page.number == n, Segment.edited.is_(True)))
                if sg.translation}
            log.info("Trabajo %s: recomponiendo la página %s (%s bloque(s) editados)", job.id, n, len(overrides))
            with SessionLocal() as cache_s:
                info = recompose_page(Path(job.document.path), Path(job.output_path),
                                      Path(job.report_path) if job.report_path else None, n, translator,
                                      SqlCache(cache_s), terms, glossary, overrides, opts, progress, should_stop)
            save_results(s, job, [info], only={n})
        options.pop("recompose_error", None)
    except Cancelled:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("Trabajo %s: no se pudo recomponer", job.id)
        s.rollback()
        options["recompose_error"] = ("No se pudo recomponer la página. " + friendly_error(e)
                                      if isinstance(e, FatalAPIError) else "No se pudo recomponer la página.")
    options.pop("recompose", None)
    job.options = options
    close_job(s, job.id, status="done", stage="done", progress=100.0, current_page=None)


def process_prepare(s, job: Job, rs, terms, opts, progress, should_stop) -> None:
    """Prepara un libro para el Playground: guarda páginas y bloques (con su protección) sin traducir nada y,
    si el libro aún no tiene glosario descubierto, lo genera para que las evaluaciones ya lo usen."""
    log.info("Trabajo %s: preparar para el Playground (sin traducir)", job.id)
    book = prepare_book(Path(job.document.path), terms, opts, progress, should_stop)
    save_results(s, job, book.pages)
    job.document.title = book.title
    s.commit()  # los bloques quedan guardados aunque falle el glosario
    if opts.discover_glossary:
        prepare_glossary(s, job, rs, terms, book, opts, progress)
    if not close_job(s, job.id, status="done", stage="done", progress=100.0, current_page=None):
        return
    log.info("Trabajo %s preparado: %s páginas, %s bloques", job.id, len(book.pages),
             sum(1 for p in book.pages for sg in p.segments if sg.action == "translate"))


def prepare_glossary(s, job: Job, rs, terms, book, opts, progress) -> None:
    """Glosario del libro al prepararlo. Si falla (sin llave, sin saldo...) el libro queda preparado igual y el
    glosario se puede generar después desde Términos."""
    try:
        translator = runtime_settings.make_translator(rs)
        segments = [sg for p in book.pages for sg in p.segments]
        domain, proposals = discover_book_glossary(segments, Protector(terms), translator, book.title,
                                                   opts.concurrency, lambda d, t: progress("glossary", d, t, None))
        n = save_auto(s, job.document, domain, proposals)
        s.commit()
        log.info("Trabajo %s: glosario con %s términos (%s)", job.id, n, domain or "sin especialidad")
    except Exception:  # noqa: BLE001
        s.rollback()
        log.exception("Trabajo %s: no se pudo generar el glosario al preparar", job.id)


def process_digitize(s, job: Job, rs, options: dict, progress, should_stop) -> None:
    """Modo digitalizar: OCR sin traducir (+ corrección opcional con el modelo) y EPUB."""
    st = get_settings()
    translator = runtime_settings.make_translator(rs) if options.get("correct") else None
    log.info("Trabajo %s: digitalizar (idioma %s, corrección %s)", job.id, options.get("ocr_lang"),
             translator.model if translator else "no")
    opts = DigitizeOptions(lang=options.get("ocr_lang", "en"), correct=bool(translator),
                           concurrency=rs.concurrency, batch_chars=st.translation_batch_chars,
                           batch_items=st.translation_batch_max_segments)
    with SessionLocal() as cache_s:
        result = run_digitize(Path(job.document.path), st.outputs_dir / f"job_{job.id}", opts, translator,
                              SqlCache(cache_s), progress, should_stop, display_name=job.document.original_name,
                              fonts_dirs=st.fonts_dirs)
    save_results(s, job, result.pages)
    job.document.title = result.title
    options["ocr_pages"] = result.report["estadisticas"]["paginas_ocr_lista"]
    job.options = options
    job.output_path, job.report_path = str(result.output_pdf), str(result.report_path)
    if not close_job(s, job.id, status="done", stage="done", progress=100.0):
        return
    log.info("Trabajo %s digitalizado: %s", job.id, result.output_pdf)
    try:
        log.info("EPUB listo: %s", build_epub_for_job(s, job))
    except Exception:  # noqa: BLE001
        log.exception("No se pudo generar el EPUB del trabajo %s", job.id)


def recover_orphans() -> None:
    """Trabajos que quedaron 'running' tras un reinicio vuelven a la cola (la caché evita repetir costos)."""
    with SessionLocal() as s:
        s.execute(text("UPDATE jobs SET status='queued' WHERE status='running'"))
        s.execute(text("UPDATE playground_runs SET status='queued' WHERE status='running'"))
        s.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    recover_orphans()
    log.info("Worker iniciado, esperando trabajos...")
    while True:
        job_id = claim_job()
        if job_id is None:
            run_id = playground.claim_run()  # el playground nunca adelanta a un libro en cola
            if run_id is not None:
                log.info("Playground: evaluación %s", run_id)
                playground.execute(run_id)
                continue
            time.sleep(2)
            continue
        log.info("Procesando trabajo %s", job_id)
        process(job_id)


if __name__ == "__main__":
    main()
