"""Prepara el bucket: lo crea si falta y aplica CORS para subidas prefirmadas desde el navegador.

    python -m app.storage.setup

Pensado para el entorno local (servicio `storage-init` del compose). En AWS/Spaces/R2 el bucket y
su CORS suelen gestionarse desde la consola o con IaC; ejecutarlo allí es opcional.
"""
import logging
import sys

from app.storage import get_storage
from app.storage.adapters.s3 import S3StorageAdapter
from app.storage.config import get_storage_settings
from app.storage.errors import StorageError


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_storage_settings()
    storage = get_storage()
    if not isinstance(storage, S3StorageAdapter):
        print(f"driver {settings.storage_driver}: nada que preparar")
        return 0
    try:
        storage.ensure_bucket(settings.cors_origins)
    except StorageError as exc:
        print(f"no se pudo preparar el bucket {settings.s3_bucket}: {exc}", file=sys.stderr)
        return 1
    print(f"bucket {settings.s3_bucket} listo (CORS: {', '.join(settings.cors_origins) or 'sin CORS'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
