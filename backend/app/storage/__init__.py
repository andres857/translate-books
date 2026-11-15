"""Almacenamiento de archivos (puertos y adaptadores). Inyectar con `Depends(get_storage)`."""
from __future__ import annotations

from functools import lru_cache

from app.storage.config import StorageSettings, get_storage_settings
from app.storage.port import StoragePort


def build_storage(settings: StorageSettings) -> StoragePort:
    if settings.storage_driver == "s3":
        from app.storage.adapters.s3 import S3StorageAdapter

        return S3StorageAdapter(settings)
    # aquí irán "local", "gcs", "azure"...
    raise ValueError(f"STORAGE_DRIVER={settings.storage_driver!r} no está implementado")


@lru_cache
def get_storage() -> StoragePort:
    return build_storage(get_storage_settings())


__all__ = ["StoragePort", "build_storage", "get_storage"]
