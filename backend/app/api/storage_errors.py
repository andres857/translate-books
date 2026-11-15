"""Errores del almacenamiento → respuestas HTTP genéricas (sin detalles internos del proveedor)."""
from __future__ import annotations

from fastapi import HTTPException

from app.storage.errors import StorageAccessDenied, StorageError, StorageNotFound, StorageUnavailable


def storage_http_error(exc: StorageError) -> HTTPException:
    if isinstance(exc, StorageNotFound):
        return HTTPException(404, "El archivo no está en el almacenamiento.")
    if isinstance(exc, StorageUnavailable):
        return HTTPException(503, "El almacenamiento no está disponible. Inténtalo de nuevo.")
    if isinstance(exc, StorageAccessDenied):
        return HTTPException(502, "Error del almacenamiento.")
    return HTTPException(502, "Error del almacenamiento.")


def storage_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except StorageError as exc:
        raise storage_http_error(exc) from None
