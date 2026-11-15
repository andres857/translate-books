"""Puerto de almacenamiento: el código de negocio solo depende de esta interfaz, nunca de un SDK."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


@dataclass(frozen=True)
class UploadResult:
    key: str
    etag: str | None = None


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    key: str
    expires_at: datetime


@dataclass(frozen=True)
class ObjectMetadata:
    size: int
    content_type: str | None = None
    last_modified: datetime | None = None


class StoragePort(ABC):
    @abstractmethod
    def upload(self, key: str, body: bytes | BinaryIO, content_type: str, size: int | None = None,
               metadata: dict[str, str] | None = None) -> UploadResult: ...

    @abstractmethod
    def presigned_upload_url(self, key: str, content_type: str, expires_in: int = 300) -> PresignedUpload: ...

    @abstractmethod
    def presigned_download_url(self, key: str, expires_in: int = 3600) -> str: ...

    @abstractmethod
    def public_url(self, key: str) -> str: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def get_metadata(self, key: str) -> ObjectMetadata | None: ...

    @abstractmethod
    def download(self, key: str) -> bytes:
        """Contenido completo del objeto (descarga multiparte en el adaptador)."""

    @abstractmethod
    def read_head(self, key: str, length: int = 64) -> bytes:
        """Primeros bytes del objeto (para comprobar el tipo real tras una subida directa)."""
