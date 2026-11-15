from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.storage_errors import storage_call
from app.config import get_settings
from app.db.models import Document, Job, Page
from app.db.session import SessionLocal, get_db
from app.pipeline.azw3 import Azw3Unavailable, azw3_path_for, build_azw3, ebook_convert_available
from app.pipeline.digitize import ocrmypdf_available
from app.pipeline.epub import build_epub_for_job, epub_path_for
from app.storage import StoragePort, get_storage
from app.storage.errors import StorageError
from app.storage.keys import generate_key

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("protect", "Protección"), ("translate", "Traducción"),
          ("rebuild", "Maquetación"), ("validate", "Validación"), ("done", "Descarga")]
STAGE_INDEX = {k: i for i, (k, _) in enumerate(STAGES)}
DIGITIZE_STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("correct", "Corrección"),
                   ("compose", "Maquetación"), ("validate", "Validación"), ("done", "Descarga")]
# preparar para el Playground: se extrae la información del libro sin traducir nada
PREPARE_STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("protect", "Protección"),
                  ("done", "Listo para evaluar")]


def _job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "No encontramos ese trabajo.")
    return job


def job_status(job: Job) -> dict:
    options = job.options or {}
    mode = options.get("mode") if options.get("mode") in ("digitize", "prepare") else "translate"
    digitize = mode == "digitize"
    stage_list = ([st for st in DIGITIZE_STAGES if st[0] != "correct" or options.get("correct")] if digitize
                  else PREPARE_STAGES if mode == "prepare" else STAGES)
    index = {k: i for i, (k, _) in enumerate(stage_list)}
    current = index.get(job.stage, 0)
    stages = []
    for i, (key, label) in enumerate(stage_list):
        if job.status == "done" or i < current:
            state = "completed"
        elif i == current:
            state = {"running": "in_progress", "queued": "pending", "failed": "error",
                     "cancelled": "cancelled", "paused": "paused"}.get(job.status, "pending")
        else:
            state = "pending"
        stages.append({"key": key, "label": label, "state": state})
    review = [{"page": p.number, "reasons": p.review_reasons} for p in job.pages if p.needs_review]
    return {
        "id": job.id,
        "mode": mode,
        "ocr_lang": options.get("ocr_lang"),
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "current_page": job.current_page,
        "page_count": job.document.page_count,
        "document_id": job.document_id,
        "original_name": job.document.original_name,
        "title_es": job.document.title_es,
        "output_name": Path(job.output_path).name if job.output_path else None,
        "error": job.error,
        "recomposing": bool(options.get("recompose")),
        "recompose_error": options.get("recompose_error"),
        "stages": stages,
        "review_pages": review,
    }


def _create_job_from_bytes(db: Session, data: bytes, filename: str, rights_confirmed: bool, source_lang: str,
                          target_lang: str, mode: str, ocr_lang: str, correct_ocr: bool) -> dict:
    """Valida el PDF, lo guarda en `uploads_dir` y encola el job (común a la subida directa y a la de S3)."""
    st = get_settings()
    if not rights_confirmed:
        raise HTTPException(400, "Debes confirmar que tienes derechos de uso sobre el libro.")
    if mode not in ("translate", "digitize", "prepare"):
        raise HTTPException(400, "Modo no válido.")
    if mode == "digitize":
        if ocr_lang not in ("en", "es", "auto"):
            raise HTTPException(400, "Idioma de OCR no válido.")
        if not ocrmypdf_available():
            raise HTTPException(400, "Este equipo no tiene OCRmyPDF/Tesseract instalados; no se puede digitalizar.")
    elif (source_lang, target_lang) != ("en", "es"):
        raise HTTPException(400, "Por ahora solo se admite traducción de inglés a español.")
    if len(data) > st.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"El archivo supera el límite de {st.max_upload_mb} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "El archivo no es un PDF válido.")
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise HTTPException(400, "No pudimos abrir el PDF. Puede estar dañado.")
    if pdf.is_encrypted or pdf.needs_pass:
        raise HTTPException(400, "El PDF está protegido con contraseña. Sube una versión sin protección.")
    if len(pdf) == 0:
        raise HTTPException(400, "El PDF no tiene páginas.")

    sha = hashlib.sha256(data).hexdigest()
    folder = st.uploads_dir / sha
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "original.pdf"
    if not path.exists():
        path.write_bytes(data)
    doc = Document(original_name=filename or "libro.pdf", path=str(path), sha256=sha, page_count=len(pdf))
    db.add(doc)
    db.flush()
    options = ({"mode": "digitize", "ocr_lang": ocr_lang, "correct": bool(correct_ocr)} if mode == "digitize"
               else {"mode": "prepare"} if mode == "prepare" else {})
    job = Job(document_id=doc.id, status="queued", stage="analyze", source_lang=source_lang, target_lang=target_lang,
              options=options)
    db.add(job)
    db.commit()
    return job_status(job)


@router.post("")
async def create_job(
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("es"),
    mode: str = Form("translate"),
    ocr_lang: str = Form("en"),
    correct_ocr: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Subida a través del backend (respaldo cuando el almacenamiento S3 no está disponible)."""
    st = get_settings()
    data = await file.read(st.max_upload_mb * 1024 * 1024 + 1)
    return _create_job_from_bytes(db, data, file.filename or "libro.pdf", rights_confirmed, source_lang, target_lang,
                                  mode, ocr_lang, correct_ocr)


# ---- subida directa del navegador a S3 con URL prefirmada (progreso real de bytes)
INCOMING = "books/incoming"


class PresignBookIn(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(gt=0)


class FromUploadIn(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    filename: str = Field(min_length=1, max_length=512)
    rights_confirmed: bool
    source_lang: str = "en"
    target_lang: str = "es"
    mode: str = "translate"
    ocr_lang: str = "en"
    correct_ocr: bool = False


def _check_book_size(size: int) -> None:
    st = get_settings()
    if size > st.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"El archivo supera el límite de {st.max_upload_mb} MB.")


@router.post("/presign")
def presign_book(body: PresignBookIn, storage: StoragePort = Depends(get_storage)):
    if not body.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se admiten archivos PDF.")
    _check_book_size(body.size)
    p = storage_call(storage.presigned_upload_url, generate_key(INCOMING, "application/pdf"), "application/pdf", 900)
    return {"url": p.url, "key": p.key, "expires_at": p.expires_at.isoformat(), "method": "PUT",
            "headers": {"Content-Type": "application/pdf"}}


@router.post("/from-upload")
def create_job_from_upload(body: FromUploadIn, storage: StoragePort = Depends(get_storage),
                           db: Session = Depends(get_db)):
    if not body.key.startswith(f"{INCOMING}/") or ".." in body.key:
        raise HTTPException(400, "Clave no válida.")
    meta = storage_call(storage.get_metadata, body.key)
    if meta is None:
        raise HTTPException(400, "No encontramos el archivo subido. Vuelve a subirlo.")
    try:
        _check_book_size(meta.size)
        data = storage_call(storage.download, body.key)
        return _create_job_from_bytes(db, data, body.filename, body.rights_confirmed, body.source_lang,
                                      body.target_lang, body.mode, body.ocr_lang, body.correct_ocr)
    finally:
        # el PDF queda en DATA_DIR; el objeto de S3 era solo un temporal
        try:
            storage.delete(body.key)
        except StorageError:
            pass


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    return [job_status(j) for j in db.query(Job).order_by(Job.id.desc()).limit(50)]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    return job_status(_job_or_404(db, job_id))


@router.get("/{job_id}/events")
async def job_events(job_id: int):
    """Progreso en tiempo real (Server-Sent Events)."""

    async def gen():
        last = None
        while True:
            with SessionLocal() as s:
                job = s.get(Job, job_id)
                if not job:
                    yield "event: error\ndata: {}\n\n"
                    return
                payload = json.dumps(job_status(job), ensure_ascii=False)
                status = job.status
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if status in ("done", "failed", "cancelled"):
                return
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        db.commit()
    return job_status(job)


@router.post("/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if job.status in ("cancelled", "failed", "paused"):
        job.status, job.error = "queued", None
        db.commit()
    return job_status(job)


@router.get("/{job_id}/download")
def download(job_id: int, format: str = "pdf", db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if job.status != "done" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(409, "El libro traducido todavía no está listo.")
    if format == "epub":
        path = _epub_for(db, job)
        return FileResponse(path, media_type="application/epub+zip", filename=path.name)
    if format == "azw3":
        path = _azw3_for(db, job)
        return FileResponse(path, media_type="application/vnd.amazon.ebook", filename=path.name)
    if format != "pdf":
        raise HTTPException(400, "Formato no disponible. Usa pdf, epub o azw3.")
    return FileResponse(job.output_path, media_type="application/pdf", filename=Path(job.output_path).name)


_epub_locks: dict[int, threading.Lock] = {}


def _epub_for(db: Session, job: Job) -> Path:
    """EPUB para Kindle: se genera desde los segmentos guardados la primera vez (o si el PDF cambió)."""
    path = epub_path_for(job.output_path)
    with _epub_locks.setdefault(job.id, threading.Lock()):
        if not path.exists() or path.stat().st_mtime < Path(job.output_path).stat().st_mtime:
            try:
                build_epub_for_job(db, job)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(500, "No se pudo generar el EPUB de este libro.") from e
    return path


def _azw3_for(db: Session, job: Job) -> Path:
    """AZW3 para Kindle: se convierte desde el EPUB con Calibre la primera vez (o si el EPUB cambió)."""
    if not ebook_convert_available():
        raise HTTPException(409, "Para descargar AZW3 hace falta Calibre en el equipo del servidor "
                                 "(sudo apt install calibre). El EPUB sigue disponible.")
    epub = _epub_for(db, job)
    path = azw3_path_for(job.output_path)
    with _epub_locks.setdefault(-job.id, threading.Lock()):
        if not path.exists() or path.stat().st_mtime < epub.stat().st_mtime:
            try:
                build_azw3(epub, path)
            except Azw3Unavailable as e:
                raise HTTPException(409, str(e)) from e
            except Exception as e:  # noqa: BLE001
                raise HTTPException(500, "No se pudo generar el AZW3 de este libro.") from e
    return path


@router.get("/{job_id}/report")
def report(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if not job.report_path or not Path(job.report_path).exists():
        raise HTTPException(409, "El reporte todavía no está listo.")
    return FileResponse(job.report_path, media_type="application/json", filename=Path(job.report_path).name)


@router.get("/{job_id}/pages/{number}/preview")
def preview(job_id: int, number: int, version: str = "translated", dpi: int = 80, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    path = job.document.path if version == "original" else job.output_path
    if not path or not Path(path).exists():
        raise HTTPException(409, "La vista previa todavía no está disponible.")
    pdf = pymupdf.open(path)
    if not 1 <= number <= len(pdf):
        raise HTTPException(404, "Esa página no existe.")
    png = pdf[number - 1].get_pixmap(dpi=max(30, min(dpi, 200))).tobytes("png")
    return Response(png, media_type="image/png")


@router.get("/{job_id}/pages")
def pages(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    rows = db.query(Page).filter(Page.job_id == job_id).order_by(Page.number)
    return [{"number": p.number, "kind": p.kind, "needs_review": p.needs_review, "reasons": p.review_reasons}
            for p in rows]
