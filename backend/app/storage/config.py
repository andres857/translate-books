"""Configuración del almacenamiento (variables de entorno, validadas al arrancar)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    storage_driver: Literal["s3"] = "s3"
    # vacío = endpoint por defecto de AWS
    s3_endpoint: str = ""
    # host con el que se firman las URL prefirmadas que usa el navegador (en Docker difiere del interno)
    s3_public_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = Field("uploads", min_length=3)
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_force_path_style: bool = True
    s3_cors_origins: str = "http://localhost:3000,http://localhost:5173"

    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080/uploads")
    upload_max_size_mb: int = Field(10, gt=0)
    upload_allowed_mime: str = "image/jpeg,image/png,image/webp,application/pdf"

    @field_validator("s3_endpoint", "s3_public_endpoint")
    @classmethod
    def _endpoint(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("debe empezar por http:// o https://")
        return v

    @property
    def allowed_mime(self) -> set[str]:
        return {m.strip() for m in self.upload_allowed_mime.split(",") if m.strip()}

    @property
    def max_size_bytes(self) -> int:
        return self.upload_max_size_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.s3_cors_origins.split(",") if o.strip()]


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
