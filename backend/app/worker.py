"""Worker local: toma trabajos de la cola (tabla jobs en SQLite) y ejecuta el pipeline.

python -m app.worker
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy import select, text

from app.config import get_settings
from app.db.cache import SqlCache
from app.db.models import Document, GlossaryEntry, Job, Page, ProtectedTerm, Segment
from app.db.session import SessionLocal
from app.pipeline.digitize import DigitizeOptions, run_digitize
from app.pipeline.epub import build_epub_for_job
from app.pipeline.runner import Cancelled, PipelineOptions, prepare_book, recompose_page, run_pipeline
from app import playground, runtime_settings
from app.pipeline.translate import FatalAPIError
from app.pipeline.types import ensure_unique_keys

log = logging.getLogger("worker")

# peso de cada etapa en el progreso global (%)
STAGE_WEIGHTS = {"analyze": (0, 4), "ocr": (4, 10), "protect": (10, 12), "translate": (12, 78),
                 "rebuild": (78, 93), "validate": (93, 100)}
# modo digitalizar (OCR sin traducir); sin corrección con el modelo, la etapa "correct" no aparece
# modo preparar (Playground): solo análisis, OCR y protección; sin traducir ni maquetar
PREPARE_WEIGHTS = {"analyze": (0, 40), "ocr": (40, 95), "protect": (95, 100)}
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


def save_results(s, job: Job, pages, only: set[int] | None = None) -> None:
    """Guarda páginas y segmentos. only: sustituir solo esas páginas (recomposición)."""
    old = s.query(Page).filter(Page.job_id == job.id)
    if only is not None:
        old = old.filter(Page.number.in_(only))
    for row in old.all():  # por el ORM, para que se borren también sus segmentos
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
        glossary = {g.source: g.target for g in s.scalars(select(GlossaryEntry).where(
            (GlossaryEntry.document_id.is_(None)) | (GlossaryEntry.document_id == doc.id)))}
        opts = PipelineOptions(min_font_scale=st.min_font_scale, min_font_size_pt=st.min_font_size_pt,
                               concurrency=rs.concurrency, batch_chars=st.translation_batch_chars,
                               batch_items=st.translation_batch_max_segments, fonts_dirs=st.fonts_dirs,
                               detect_names=rs.provider != "fake")
        if prepare:  # sin traductor: preparar no necesita llave ni llama a ningún modelo
            process_prepare(s, job, terms, opts, progress, should_stop)
            return
        translator = runtime_settings.make_translator(rs)
        if options.get("recompose"):
            process_recompose(s, job, options, translator, terms, glossary, opts, progress, should_stop)
            return
        log.info("Trabajo %s: modo de traducción %s (%s)", job_id, rs.provider, translator.model)
        out_dir = st.outputs_dir / f"job_{job.id}"
        result = run_pipeline(Path(doc.path), out_dir, translator, SqlCache(SessionLocal()), terms, glossary,
                              opts, progress, should_stop)
        save_results(s, job, result.pages)
        doc.title, doc.title_es = result.title, result.title_es
        job.output_path, job.report_path = str(result.output_pdf), str(result.report_path)
        job.status, job.stage, job.progress = "done", "done", 100.0
        s.commit()
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
        job = s.get(Job, job_id)
        job.status, job.error = "failed", friendly_error(e)
        s.commit()
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
            info = recompose_page(Path(job.document.path), Path(job.output_path),
                                  Path(job.report_path) if job.report_path else None, n, translator,
                                  SqlCache(SessionLocal()), terms, glossary, overrides, opts, progress, should_stop)
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
    job.status, job.stage, job.progress, job.current_page = "done", "done", 100.0, None
    s.commit()


def process_prepare(s, job: Job, terms, opts, progress, should_stop) -> None:
    """Prepara un libro para el Playground: guarda páginas y bloques (con su protección) sin traducir nada."""
    log.info("Trabajo %s: preparar para el Playground (sin traducir)", job.id)
    book = prepare_book(Path(job.document.path), terms, opts, progress, should_stop)
    save_results(s, job, book.pages)
    job.document.title = book.title
    job.status, job.stage, job.progress, job.current_page = "done", "done", 100.0, None
    s.commit()
    log.info("Trabajo %s preparado: %s páginas, %s bloques", job.id, len(book.pages),
             sum(1 for p in book.pages for sg in p.segments if sg.action == "translate"))


def process_digitize(s, job: Job, rs, options: dict, progress, should_stop) -> None:
    """Modo digitalizar: OCR sin traducir (+ corrección opcional con el modelo) y EPUB."""
    st = get_settings()
    translator = runtime_settings.make_translator(rs) if options.get("correct") else None
    log.info("Trabajo %s: digitalizar (idioma %s, corrección %s)", job.id, options.get("ocr_lang"),
             translator.model if translator else "no")
    opts = DigitizeOptions(lang=options.get("ocr_lang", "en"), correct=bool(translator),
                           concurrency=rs.concurrency, batch_chars=st.translation_batch_chars,
                           batch_items=st.translation_batch_max_segments)
    result = run_digitize(Path(job.document.path), st.outputs_dir / f"job_{job.id}", opts, translator,
                          SqlCache(SessionLocal()), progress, should_stop, display_name=job.document.original_name,
                          fonts_dirs=st.fonts_dirs)
    save_results(s, job, result.pages)
    job.document.title = result.title
    options["ocr_pages"] = result.report["estadisticas"]["paginas_ocr_lista"]
    job.options = options
    job.output_path, job.report_path = str(result.output_pdf), str(result.report_path)
    job.status, job.stage, job.progress = "done", "done", 100.0
    s.commit()
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
