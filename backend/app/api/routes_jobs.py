from __future__ import annotations

import hashlib
import threading
import weakref
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, object_session

from app.api.schemas import JobRead, OkOut, PageRead, PresignBookOut
from app.api.storage_errors import storage_call
from app.auth.deps import Principal, require_admin, require_user
from app.config import get_settings
from app.db.models import Document, Job, Page
from app.db.session import get_db
from app.jobs_service import delete_job_and_files, ensure_not_busy, get_visible_job
from app.pipeline.azw3 import Azw3Unavailable, azw3_path_for, build_azw3, ebook_convert_available
from app.pipeline.digitize import ocrmypdf_available
from app.pipeline.epub import build_epub_for_job, epub_path_for
from app.storage import StoragePort, get_storage
from app.storage.errors import StorageError
from app.storage.keys import generate_key

JobMode = Literal["translate", "digitize", "prepare"]
OcrLang = Literal["en", "es", "auto"]

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("protect", "Protección"), ("glossary", "Glosario"),
          ("translate", "Traducción"),
          ("rebuild", "Maquetación"), ("validate", "Validación"), ("done", "Descarga")]
STAGE_INDEX = {k: i for i, (k, _) in enumerate(STAGES)}
DIGITIZE_STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("correct", "Corrección"),
                   ("compose", "Maquetación"), ("validate", "Validación"), ("done", "Descarga")]
# preparar para el Playground: se extrae la información del libro sin traducir nada
PREPARE_STAGES = [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("protect", "Protección"),
                  ("glossary", "Glosario"), ("done", "Listo para evaluar")]


def _review_pages(db: Session, job_ids: list[int]) -> dict[int, list[dict]]:
    """Páginas a revisar de varios trabajos en una sola consulta (solo `number` y `review_reasons`, filtrando
    `needs_review`), en el mismo orden que la relación `Job.pages`."""
    out: dict[int, list[dict]] = {i: [] for i in job_ids}
    if not job_ids:
        return out
    rows = db.execute(select(Page.job_id, Page.number, Page.review_reasons)
                      .where(Page.job_id.in_(job_ids), Page.needs_review.is_(True)).order_by(Page.id))
    for job_id, number, reasons in rows:
        out[job_id].append({"page": number, "reasons": reasons})
    return out


def job_status(job: Job, review: list[dict] | None = None) -> dict:
    """Estado del trabajo para la API. `review` (páginas a revisar) se puede pasar ya calculado (listado);
    si no, se consulta sin cargar todas las páginas."""
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
    if review is None:
        db = object_session(job)
        review = (_review_pages(db, [job.id])[job.id] if db is not None
                  else [{"page": p.number, "reasons": p.review_reasons} for p in job.pages if p.needs_review])
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
                          target_lang: str, mode: JobMode, ocr_lang: OcrLang, correct_ocr: bool, p: Principal) -> dict:
    """Valida el PDF, lo guarda en `uploads_dir` y encola el job (común a la subida directa y a la de S3)."""
    st = get_settings()
    if not rights_confirmed:
        raise HTTPException(400, "Debes confirmar que tienes derechos de uso sobre el libro.")
    if mode == "prepare" and not p.is_admin:  # preparar es para el Playground (administración)
        raise HTTPException(403, "No tienes permiso para esta acción.")
    if mode == "digitize":
        if not ocrmypdf_available():
            raise HTTPException(400, "Este equipo no tiene OCRmyPDF/Tesseract instalados; no se puede digitalizar.")
    elif (source_lang, target_lang) != ("en", "es"):
        raise HTTPException(400, "Por ahora solo se admite traducción de inglés a español.")
    if len(data) > st.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"El archivo supera el límite de {st.max_upload_mb} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "El archivo no es un PDF válido.")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            encrypted, page_count = pdf.is_encrypted or pdf.needs_pass, len(pdf)
    except Exception:
        raise HTTPException(400, "No pudimos abrir el PDF. Puede estar dañado.")
    if encrypted:
        raise HTTPException(400, "El PDF está protegido con contraseña. Sube una versión sin protección.")
    if page_count == 0:
        raise HTTPException(400, "El PDF no tiene páginas.")

    sha = hashlib.sha256(data).hexdigest()
    folder = st.uploads_dir / sha
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "original.pdf"
    if not path.exists():
        path.write_bytes(data)
    doc = Document(original_name=filename or "libro.pdf", path=str(path), sha256=sha, page_count=page_count)
    db.add(doc)
    db.flush()
    options = ({"mode": "digitize", "ocr_lang": ocr_lang, "correct": bool(correct_ocr)} if mode == "digitize"
               else {"mode": "prepare"} if mode == "prepare" else {})
    job = Job(document_id=doc.id, status="queued", stage="analyze", source_lang=source_lang, target_lang=target_lang,
              options=options, owner_id=p.user.id)
    db.add(job)
    db.commit()
    return job_status(job)


@router.post("", response_model=JobRead)
def create_job(
    file: UploadFile = File(...),
    rights_confirmed: bool = Form(...),
    source_lang: str = Form("en", max_length=8),
    target_lang: str = Form("es", max_length=8),
    mode: JobMode = Form("translate"),
    ocr_lang: OcrLang = Form("en"),
    correct_ocr: bool = Form(False),
    db: Session = Depends(get_db),
    p: Principal = Depends(require_user),
):
    """Subida a través del backend (respaldo cuando el almacenamiento S3 no está disponible).

    Es `def`: FastAPI la ejecuta en el threadpool y abrir el PDF, el SHA-256, la escritura y la BD no bloquean el
    event loop."""
    st = get_settings()
    data = file.file.read(st.max_upload_mb * 1024 * 1024 + 1)
    return _create_job_from_bytes(db, data, file.filename or "libro.pdf", rights_confirmed, source_lang, target_lang,
                                  mode, ocr_lang, correct_ocr, p)


# ---- subida directa del navegador a S3 con URL prefirmada (progreso real de bytes)
INCOMING = "books/incoming"


class PresignBookIn(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(gt=0)


class FromUploadIn(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    filename: str = Field(min_length=1, max_length=512)
    rights_confirmed: bool
    source_lang: str = Field(default="en", max_length=8)
    target_lang: str = Field(default="es", max_length=8)
    mode: JobMode = "translate"
    ocr_lang: OcrLang = "en"
    correct_ocr: bool = False


def _check_book_size(size: int) -> None:
    st = get_settings()
    if size > st.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"El archivo supera el límite de {st.max_upload_mb} MB.")


def _incoming(p: Principal) -> str:
    """Cada usuario sube a su propia carpeta temporal: from-upload no acepta claves de otro."""
    return f"{INCOMING}/u{p.user.id}"


@router.post("/presign", response_model=PresignBookOut)
def presign_book(body: PresignBookIn, storage: StoragePort = Depends(get_storage),
                 p: Principal = Depends(require_user)):
    if not body.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se admiten archivos PDF.")
    _check_book_size(body.size)
    presigned = storage_call(storage.presigned_upload_url, generate_key(_incoming(p), "application/pdf"),
                             "application/pdf", 900)
    return {"url": presigned.url, "key": presigned.key, "expires_at": presigned.expires_at.isoformat(), "method": "PUT",
            "headers": {"Content-Type": "application/pdf"}}


@router.post("/from-upload", response_model=JobRead)
def create_job_from_upload(body: FromUploadIn, storage: StoragePort = Depends(get_storage),
                           db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    if not body.key.startswith(f"{_incoming(p)}/") or ".." in body.key:
        raise HTTPException(400, "Clave no válida.")
    meta = storage_call(storage.get_metadata, body.key)
    if meta is None:
        raise HTTPException(400, "No encontramos el archivo subido. Vuelve a subirlo.")
    try:
        _check_book_size(meta.size)
        data = storage_call(storage.download, body.key)
        return _create_job_from_bytes(db, data, body.filename, body.rights_confirmed, body.source_lang,
                                      body.target_lang, body.mode, body.ocr_lang, body.correct_ocr, p)
    finally:
        # el PDF queda en DATA_DIR; el objeto de S3 era solo un temporal
        try:
            storage.delete(body.key)
        except StorageError:
            pass


@router.get("", response_model=list[JobRead])
def list_jobs(db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    q = select(Job).options(joinedload(Job.document))
    if not p.is_admin:
        q = q.where(Job.owner_id == p.user.id)
    jobs = db.scalars(q.order_by(Job.id.desc()).limit(50)).all()
    review = _review_pages(db, [j.id for j in jobs])
    return [job_status(j, review[j.id]) for j in jobs]


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    return job_status(get_visible_job(db, job_id, p))


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    job = get_visible_job(db, job_id, p)
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        db.commit()
    return job_status(job)


@router.delete("/{job_id}", response_model=OkOut)
def delete_job(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_admin)):
    """Elimina un libro con todo lo suyo: páginas y bloques, evaluaciones del Playground, archivos generados y,
    si el documento no tiene otro trabajo, el documento con su glosario, términos y PDF subido."""
    job = get_visible_job(db, job_id, p)
    ensure_not_busy(db, job)
    delete_job_and_files(db, job)
    return {"ok": True}


@router.post("/{job_id}/resume", response_model=JobRead)
def resume_job(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    job = get_visible_job(db, job_id, p)
    if job.status in ("cancelled", "failed", "paused"):
        job.status, job.error = "queued", None
        db.commit()
    return job_status(job)


@router.get("/{job_id}/download")
def download(job_id: int, format: Literal["pdf", "epub", "azw3"] = "pdf", db: Session = Depends(get_db),
             p: Principal = Depends(require_user)):
    job = get_visible_job(db, job_id, p)
    if job.status != "done" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(409, "El libro traducido todavía no está listo.")
    if format == "epub":
        path = _epub_for(db, job)
        return FileResponse(path, media_type="application/epub+zip", filename=path.name)
    if format == "azw3":
        path = _azw3_for(db, job)
        return FileResponse(path, media_type="application/vnd.amazon.ebook", filename=path.name)
    return FileResponse(job.output_path, media_type="application/pdf", filename=Path(job.output_path).name)


# Un lock por (formato, trabajo) mientras alguien lo usa: el diccionario solo guarda referencias débiles, así que
# la entrada desaparece cuando ninguna descarga la retiene (no crece con cada trabajo descargado).
_build_locks: weakref.WeakValueDictionary[tuple[str, int], threading.Lock] = weakref.WeakValueDictionary()
_build_locks_guard = threading.Lock()


def _build_lock(kind: str, job_id: int) -> threading.Lock:
    """El mismo lock para todas las descargas simultáneas de un formato de un trabajo."""
    with _build_locks_guard:  # get + set no es atómico en WeakValueDictionary
        lock = _build_locks.get((kind, job_id))
        if lock is None:
            lock = _build_locks[(kind, job_id)] = threading.Lock()
        return lock


def _epub_for(db: Session, job: Job) -> Path:
    """EPUB para Kindle: se genera desde los segmentos guardados la primera vez (o si el PDF cambió)."""
    path = epub_path_for(job.output_path)
    with _build_lock("epub", job.id):
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
    with _build_lock("azw3", job.id):
        if not path.exists() or path.stat().st_mtime < epub.stat().st_mtime:
            try:
                build_azw3(epub, path)
            except Azw3Unavailable as e:
                raise HTTPException(409, str(e)) from e
            except Exception as e:  # noqa: BLE001
                raise HTTPException(500, "No se pudo generar el AZW3 de este libro.") from e
    return path


@router.get("/{job_id}/report")
def report(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    job = get_visible_job(db, job_id, p)
    if not job.report_path or not Path(job.report_path).exists():
        raise HTTPException(409, "El reporte todavía no está listo.")
    return FileResponse(job.report_path, media_type="application/json", filename=Path(job.report_path).name)


@router.get("/{job_id}/pages/{number}/preview")
def preview(job_id: int, number: int, version: Literal["original", "translated"] = "translated", dpi: int = 80,
            db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    job = get_visible_job(db, job_id, p)
    path = job.document.path if version == "original" else job.output_path
    if not path or not Path(path).exists():
        raise HTTPException(409, "La vista previa todavía no está disponible.")
    with pymupdf.open(path) as pdf:
        if not 1 <= number <= len(pdf):
            raise HTTPException(404, "Esa página no existe.")
        png = pdf[number - 1].get_pixmap(dpi=max(30, min(dpi, 200))).tobytes("png")
    return Response(png, media_type="image/png")


@router.get("/{job_id}/pages", response_model=list[PageRead])
def pages(job_id: int, db: Session = Depends(get_db), p: Principal = Depends(require_user)):
    get_visible_job(db, job_id, p)
    rows = db.scalars(select(Page).where(Page.job_id == job_id).order_by(Page.number))
    return [{"number": pg.number, "kind": pg.kind, "needs_review": pg.needs_review, "reasons": pg.review_reasons}
            for pg in rows]
