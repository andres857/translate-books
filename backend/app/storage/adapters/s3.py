"""Adaptador S3 (SeaweedFS, AWS S3, DigitalOcean Spaces, Cloudflare R2). Único módulo que importa boto3.

Sin ACL por objeto (R2 no las soporta): el acceso público se da a nivel de bucket/dominio y
`public_url()` solo concatena PUBLIC_BASE_URL + key.
"""
from __future__ import annotations

import io
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import BinaryIO

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from botocore.exceptions import ConnectionError as BotoConnectionError

from app.storage.config import StorageSettings
from app.storage.errors import StorageAccessDenied, StorageError, StorageNotFound, StorageUnavailable
from app.storage.port import ObjectMetadata, PresignedUpload, StoragePort, UploadResult

log = logging.getLogger("app.storage")

_NOT_FOUND = {"NoSuchKey", "NotFound", "404", "NoSuchBucket"}
_DENIED = {"AccessDenied", "403", "Forbidden", "InvalidAccessKeyId", "SignatureDoesNotMatch"}
_UNAVAILABLE = (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, BotoConnectionError)


def _map_error(exc: Exception) -> StorageError:
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in _NOT_FOUND:
            return StorageNotFound("objeto no encontrado")
        if code in _DENIED:
            return StorageAccessDenied("acceso denegado al almacenamiento")
        if code in {"SlowDown", "ServiceUnavailable", "503", "RequestTimeout"}:
            return StorageUnavailable("almacenamiento no disponible")
        return StorageError(f"error del almacenamiento ({code or 'desconocido'})")
    if isinstance(exc, _UNAVAILABLE):
        return StorageUnavailable("almacenamiento no disponible")
    return StorageError("error del almacenamiento")


class S3StorageAdapter(StoragePort):
    def __init__(self, settings: StorageSettings):
        self.settings = settings
        self.bucket = settings.s3_bucket
        self._base_url = str(settings.public_base_url).rstrip("/")
        cfg = Config(signature_version="s3v4", s3={"addressing_style": "path" if settings.s3_force_path_style
                                                   else "virtual"},
                     connect_timeout=5, read_timeout=60, retries={"max_attempts": 3, "mode": "standard"})
        common = dict(region_name=settings.s3_region, config=cfg,
                      aws_access_key_id=settings.s3_access_key.get_secret_value() or None,
                      aws_secret_access_key=settings.s3_secret_key.get_secret_value() or None)
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint or None, **common)
        # las URL prefirmadas firman el host: se firman con el endpoint que ve el navegador
        public = settings.s3_public_endpoint
        self.presign_client = (boto3.client("s3", endpoint_url=public, **common)
                               if public and public != settings.s3_endpoint else self.client)
        self.transfer = TransferConfig(multipart_threshold=8 * 1024 * 1024, multipart_chunksize=8 * 1024 * 1024)

    @contextmanager
    def _op(self, name: str, key: str | None = None, **extra):
        t0 = time.perf_counter()
        try:
            yield
        except (ClientError, BotoCoreError) as exc:
            err = _map_error(exc)
            level = logging.INFO if isinstance(err, StorageNotFound) else logging.WARNING
            log.log(level, "storage %s falló key=%s error=%s", name, key, type(err).__name__)
            raise err from None
        log.info("storage %s key=%s %s%.0fms", name, key,
                 "".join(f"{k}={v} " for k, v in extra.items()), (time.perf_counter() - t0) * 1000)

    # ---- StoragePort
    def upload(self, key, body, content_type, size=None, metadata=None) -> UploadResult:
        fileobj: BinaryIO = io.BytesIO(body) if isinstance(body, (bytes, bytearray)) else body
        size = size if size is not None else (len(body) if isinstance(body, (bytes, bytearray)) else None)
        with self._op("upload", key, size=size):
            # upload_fileobj: multipart y en streaming a partir de multipart_threshold
            self.client.upload_fileobj(fileobj, self.bucket, key, Config=self.transfer,
                                       ExtraArgs={"ContentType": content_type, "Metadata": metadata or {}})
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        return UploadResult(key=key, etag=(head.get("ETag") or "").strip('"') or None)

    def presigned_upload_url(self, key, content_type, expires_in=300) -> PresignedUpload:
        with self._op("presign_put", key):
            url = self.presign_client.generate_presigned_url(
                "put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires_in)
        return PresignedUpload(url=url, key=key, expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in))

    def presigned_download_url(self, key, expires_in=3600) -> str:
        with self._op("presign_get", key):
            return self.presign_client.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in)

    def public_url(self, key) -> str:
        return f"{self._base_url}/{key.lstrip('/')}"

    def delete(self, key) -> None:
        with self._op("delete", key):
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key) -> bool:
        return self.get_metadata(key) is not None

    def get_metadata(self, key) -> ObjectMetadata | None:
        try:
            with self._op("head", key):
                h = self.client.head_object(Bucket=self.bucket, Key=key)
        except StorageNotFound:
            return None
        return ObjectMetadata(size=int(h.get("ContentLength", 0)), content_type=h.get("ContentType"),
                              last_modified=h.get("LastModified"))

    def download(self, key) -> bytes:
        buf = io.BytesIO()
        with self._op("download", key):
            self.client.download_fileobj(self.bucket, key, buf, Config=self.transfer)
        return buf.getvalue()

    def read_head(self, key, length=64) -> bytes:
        with self._op("read_head", key):
            r = self.client.get_object(Bucket=self.bucket, Key=key, Range=f"bytes=0-{length - 1}")
            return r["Body"].read()

    # ---- preparación (dev): bucket + CORS
    def ensure_bucket(self, cors_origins: list[str]) -> None:
        with self._op("ensure_bucket", self.bucket):
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code")) not in _NOT_FOUND:
                    raise
                self.client.create_bucket(Bucket=self.bucket)
            if cors_origins:
                self.client.put_bucket_cors(Bucket=self.bucket, CORSConfiguration={"CORSRules": [{
                    "AllowedOrigins": cors_origins, "AllowedMethods": ["PUT", "GET", "HEAD"],
                    "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 3000}]})
