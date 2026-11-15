"""Archivos de usuario sobre StoragePort (sin dependencias del proveedor)."""
from __future__ import annotations

import logging
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.db.models import StoredFile
from app.storage.config import StorageSettings
from app.storage.errors import StorageNotFound
from app.storage.keys import generate_key
from app.storage.port import StoragePort
from app.storage.sniff import sniff_mime

log = logging.getLogger("app.files")
FOLDER = "files"
PRESIGN_SECONDS = 300
PRIVATE_URL_SECONDS = 3600


class FileValidationError(ValueError):
    """Entrada no válida (se responde 400/413)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class FileNotFound(LookupError):
    pass


class FilesService:
    def __init__(self, storage: StoragePort, db: Session, settings: StorageSettings):
        self.storage, self.db, self.settings = storage, db, settings

    # ---- validación
    def _check(self, content_type: str, size: int) -> None:
        if content_type not in self.settings.allowed_mime:
            raise FileValidationError("Tipo de archivo no permitido.")
        if size <= 0:
            raise FileValidationError("El archivo está vacío.")
        if size > self.settings.max_size_bytes:
            raise FileValidationError(f"El archivo supera el límite de {self.settings.upload_max_size_mb} MB.", 413)

    def _check_magic(self, head: bytes, content_type: str) -> None:
        if sniff_mime(head) != content_type:
            raise FileValidationError("El contenido del archivo no coincide con su tipo.")

    def url_for(self, f: StoredFile) -> str:
        return (self.storage.presigned_download_url(f.key, PRIVATE_URL_SECONDS) if f.private
                else self.storage.public_url(f.key))

    def _payload(self, f: StoredFile) -> dict:
        return {"id": f.id, "key": f.key, "url": self.url_for(f), "original_name": f.original_name,
                "content_type": f.content_type, "size": f.size, "private": f.private}

    def _register(self, key: str, filename: str, content_type: str, size: int, private: bool) -> StoredFile:
        f = StoredFile(key=key, original_name=filename[:512] or "archivo", content_type=content_type, size=size,
                       private=private)
        self.db.add(f)
        self.db.commit()
        return f

    # ---- casos de uso
    def upload(self, data: bytes, filename: str, content_type: str, private: bool = False) -> dict:
        self._check(content_type, len(data))
        self._check_magic(data[:16], content_type)
        key = generate_key(FOLDER, content_type)
        # metadata S3 solo admite ASCII: el nombre original va codificado
        self.storage.upload(key, data, content_type, size=len(data),
                            metadata={"original-name": quote(filename or "archivo", safe="")})
        return self._payload(self._register(key, filename, content_type, len(data), private))

    def presign(self, filename: str, content_type: str, size: int) -> dict:
        self._check(content_type, size)
        p = self.storage.presigned_upload_url(generate_key(FOLDER, content_type), content_type, PRESIGN_SECONDS)
        return {"url": p.url, "key": p.key, "expires_at": p.expires_at.isoformat(), "method": "PUT",
                "headers": {"Content-Type": content_type}}

    def confirm(self, key: str, filename: str, content_type: str, size: int, private: bool = False) -> dict:
        if not key.startswith(f"{FOLDER}/") or ".." in key:
            raise FileValidationError("Clave no válida.")
        self._check(content_type, size)
        if self.db.query(StoredFile).filter_by(key=key).first():
            raise FileValidationError("Ese archivo ya está registrado.", 409)
        meta = self.storage.get_metadata(key)
        if meta is None:
            raise FileValidationError("No encontramos el archivo subido.")
        try:
            if meta.size != size or (meta.content_type or "").split(";")[0] != content_type:
                raise FileValidationError("El archivo subido no coincide con lo declarado.")
            self._check(content_type, meta.size)
            self._check_magic(self.storage.read_head(key, 16), content_type)
        except FileValidationError:
            # no dejar huérfanos que no cumplen las reglas
            self.storage.delete(key)
            raise
        return self._payload(self._register(key, filename, content_type, meta.size, private))

    def get(self, file_id: int) -> dict:
        return self._payload(self._get(file_id))

    def delete(self, file_id: int) -> None:
        f = self._get(file_id)
        try:
            self.storage.delete(f.key)
        except StorageNotFound:
            pass
        self.db.delete(f)
        self.db.commit()
        log.info("archivo %s borrado key=%s", file_id, f.key)

    def _get(self, file_id: int) -> StoredFile:
        f = self.db.get(StoredFile, file_id)
        if not f:
            raise FileNotFound(file_id)
        return f
