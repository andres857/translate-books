"""Integración del S3StorageAdapter contra el SeaweedFS del compose (`docker compose up -d seaweedfs cdn`).

Se salta si el S3 local no responde. Variables: S3_TEST_ENDPOINT (def. http://localhost:8333),
S3_TEST_CDN (def. PUBLIC_BASE_URL del .env).
"""
import os
import uuid

import httpx
import pytest

from app.storage.adapters.s3 import S3StorageAdapter
from app.storage.config import StorageSettings
from app.storage.errors import StorageNotFound

ENDPOINT = os.environ.get("S3_TEST_ENDPOINT", "http://localhost:8333")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

pytestmark = pytest.mark.s3


def _reachable() -> bool:
    try:
        httpx.get(ENDPOINT, timeout=2)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="module")
def storage():
    if not _reachable():
        pytest.skip(f"SeaweedFS no responde en {ENDPOINT}")
    st = StorageSettings(s3_endpoint=ENDPOINT, s3_public_endpoint="")
    if not st.s3_access_key.get_secret_value():
        pytest.skip("faltan S3_ACCESS_KEY/S3_SECRET_KEY en .env")
    adapter = S3StorageAdapter(st)
    adapter.ensure_bucket(["http://localhost:5173"])
    return adapter


@pytest.fixture
def key():
    return f"tests/{uuid.uuid4().hex}.png"


def test_upload_metadata_delete(storage, key):
    r = storage.upload(key, PNG, "image/png", metadata={"original-name": "foto.png"})
    assert r.key == key and r.etag
    assert storage.exists(key)
    meta = storage.get_metadata(key)
    assert meta.size == len(PNG) and meta.content_type == "image/png" and meta.last_modified
    assert storage.read_head(key, 8) == PNG[:8]
    assert storage.download(key) == PNG
    storage.delete(key)
    assert not storage.exists(key) and storage.get_metadata(key) is None


def test_missing_object_maps_to_not_found(storage):
    with pytest.raises(StorageNotFound):
        storage.read_head("tests/no-existe.png")


def test_multipart_streaming_upload(storage, key):
    import io

    body = PNG + os.urandom(9 * 1024 * 1024)  # > multipart_threshold (8 MB)
    storage.upload(key, io.BytesIO(body), "image/png")
    assert storage.get_metadata(key).size == len(body)
    storage.delete(key)


def test_presigned_put_and_get(storage, key):
    up = storage.presigned_upload_url(key, "image/png", expires_in=60)
    r = httpx.put(up.url, content=PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 200, r.text
    r = httpx.get(storage.presigned_download_url(key, 60))
    assert r.status_code == 200 and r.content == PNG
    # preflight CORS del navegador para la subida directa
    r = httpx.options(up.url, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    storage.delete(key)


def test_cdn_cache_hit(storage, key):
    storage.upload(key, PNG, "image/png")
    url = os.environ.get("S3_TEST_CDN") or storage.public_url(key)
    try:
        first = httpx.get(url, timeout=5)
    except httpx.HTTPError:
        pytest.skip("CDN local no responde")
    second = httpx.get(url, timeout=5)
    assert first.status_code == 200 and first.content == PNG
    assert first.headers["x-cache-status"] == "MISS" and second.headers["x-cache-status"] == "HIT"
    assert "max-age=604800" in second.headers["cache-control"]
    storage.delete(key)
