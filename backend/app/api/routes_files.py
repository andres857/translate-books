"""Archivos en el almacenamiento S3: subida vía backend, subida directa prefirmada, consulta y borrado."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.files_service import FileNotFound, FilesService, FileValidationError
from app.storage import StoragePort, get_storage
from app.storage.config import get_storage_settings
from app.api.storage_errors import storage_http_error
from app.storage.errors import StorageError

router = APIRouter(prefix="/api/files", tags=["files"])


def get_files_service(storage: StoragePort = Depends(get_storage), db: Session = Depends(get_db)) -> FilesService:
    return FilesService(storage, db, get_storage_settings())


def _run(fn, *args, **kwargs):
    """Errores de negocio y de storage → HTTP, sin filtrar detalles internos."""
    try:
        return fn(*args, **kwargs)
    except FileValidationError as e:
        raise HTTPException(e.status, str(e))
    except FileNotFound:
        raise HTTPException(404, "No encontramos ese archivo.")
    except StorageError as exc:
        raise storage_http_error(exc) from None


class PresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    contentType: str
    size: int = Field(gt=0)


class ConfirmIn(PresignIn):
    key: str = Field(min_length=1, max_length=512)
    private: bool = False


@router.post("")
async def upload_file(file: UploadFile = File(...), private: bool = Form(False),
                      svc: FilesService = Depends(get_files_service)):
    limit = svc.settings.max_size_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"El archivo supera el límite de {svc.settings.upload_max_size_mb} MB.")
    content_type = (file.content_type or "").split(";")[0].strip()
    return _run(svc.upload, data, file.filename or "archivo", content_type, private)


@router.post("/presign")
def presign(body: PresignIn, svc: FilesService = Depends(get_files_service)):
    return _run(svc.presign, body.filename, body.contentType, body.size)


@router.post("/confirm")
def confirm(body: ConfirmIn, svc: FilesService = Depends(get_files_service)):
    return _run(svc.confirm, body.key, body.filename, body.contentType, body.size, body.private)


@router.get("/{file_id}")
def get_file(file_id: int, svc: FilesService = Depends(get_files_service)):
    return _run(svc.get, file_id)


@router.delete("/{file_id}", status_code=204)
def delete_file(file_id: int, svc: FilesService = Depends(get_files_service)):
    _run(svc.delete, file_id)
