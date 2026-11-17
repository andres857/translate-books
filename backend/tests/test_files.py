"""Endpoints /api/files y FilesService con un StoragePort falso en memoria."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.storage.errors import StorageNotFound, StorageUnavailable
from app.storage.port import ObjectMetadata, PresignedUpload, StoragePort, UploadResult

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
PDF = b"%PDF-1.7\n" + b"x" * 50


class FakeStorage(StoragePort):
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail = False

    def _guard(self):
        if self.fail:
            raise StorageUnavailable("caído")

    def upload(self, key, body, content_type, size=None, metadata=None):
        self._guard()
        self.objects[key] = (body if isinstance(body, bytes) else body.read(), content_type)
        return UploadResult(key=key, etag="e")

    def presigned_upload_url(self, key, content_type, expires_in=300):
        return PresignedUpload(url=f"http://s3.test/uploads/{key}?sig=put", key=key,
                               expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in))

    def presigned_download_url(self, key, expires_in=3600):
        return f"http://s3.test/uploads/{key}?sig=get"

    def public_url(self, key):
        return f"http://cdn.test/uploads/{key}"

    def delete(self, key):
        self.objects.pop(key, None)

    def exists(self, key):
        return key in self.objects

    def get_metadata(self, key):
        if key not in self.objects:
            return None
        data, ct = self.objects[key]
        return ObjectMetadata(size=len(data), content_type=ct)

    def download(self, key):
        if key not in self.objects:
            raise StorageNotFound(key)
        return self.objects[key][0]

    def read_head(self, key, length=64):
        if key not in self.objects:
            raise StorageNotFound(key)
        return self.objects[key][0][:length]


@pytest.fixture(scope="module")
def app_client(tmp_path_factory):
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ["UPLOAD_MAX_SIZE_MB"] = "1"
    from app.config import get_settings
    from app.storage.config import get_storage_settings

    get_settings.cache_clear()
    get_storage_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from app.main import app
    from app.storage import get_storage

    from .conftest import admin_client

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield admin_client(app), fake
    app.dependency_overrides.pop(get_storage, None)
    os.environ.pop("UPLOAD_MAX_SIZE_MB")
    get_storage_settings.cache_clear()


@pytest.fixture
def client(app_client):
    c, fake = app_client
    fake.fail = False
    return c


@pytest.fixture
def storage(app_client):
    return app_client[1]


def test_upload_get_delete(client, storage):
    r = client.post("/api/files", files={"file": ("Mi foto ñ.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    key = body["key"]
    assert key.startswith("files/") and key.endswith(".png") and "foto" not in key
    assert body["url"] == f"http://cdn.test/uploads/{key}"
    assert storage.objects[key][0] == PNG
    r = client.get(f"/api/files/{body['id']}")
    assert r.json()["url"] == body["url"] and r.json()["original_name"] == "Mi foto ñ.png"
    assert client.delete(f"/api/files/{body['id']}").status_code == 204
    assert key not in storage.objects
    assert client.get(f"/api/files/{body['id']}").status_code == 404


def test_private_file_gets_presigned_url(client):
    r = client.post("/api/files", files={"file": ("doc.pdf", PDF, "application/pdf")}, data={"private": "true"})
    assert r.status_code == 200 and "sig=get" in r.json()["url"]


def test_rejects_disallowed_mime(client):
    r = client.post("/api/files", files={"file": ("a.txt", b"hola", "text/plain")})
    assert r.status_code == 400


def test_rejects_spoofed_magic_bytes(client, storage):
    before = dict(storage.objects)
    r = client.post("/api/files", files={"file": ("x.png", PDF, "image/png")})
    assert r.status_code == 400 and "no coincide" in r.json()["detail"]
    assert storage.objects == before


def test_rejects_too_large(client):
    r = client.post("/api/files", files={"file": ("big.png", PNG + b"\x00" * (1024 * 1024), "image/png")})
    assert r.status_code == 413


def test_presign_and_confirm(client, storage):
    r = client.post("/api/files/presign", json={"filename": "a.png", "contentType": "image/png", "size": len(PNG)})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["method"] == "PUT" and "sig=put" in p["url"] and p["key"].startswith("files/")
    # sin subir todavía
    payload = {"key": p["key"], "filename": "a.png", "contentType": "image/png", "size": len(PNG)}
    assert client.post("/api/files/confirm", json=payload).status_code == 400
    storage.objects[p["key"]] = (PNG, "image/png")  # simula el PUT del navegador
    r = client.post("/api/files/confirm", json=payload)
    assert r.status_code == 200 and r.json()["url"].startswith("http://cdn.test/")
    assert client.post("/api/files/confirm", json=payload).status_code == 409


def test_confirm_size_mismatch_removes_object(client, storage):
    key = client.post("/api/files/presign", json={"filename": "a.png", "contentType": "image/png",
                                                 "size": len(PNG)}).json()["key"]
    storage.objects[key] = (PNG + b"extra", "image/png")
    r = client.post("/api/files/confirm", json={"key": key, "filename": "a.png", "contentType": "image/png",
                                                "size": len(PNG)})
    assert r.status_code == 400 and key not in storage.objects


def test_confirm_rejects_foreign_key(client):
    r = client.post("/api/files/confirm", json={"key": "otra/cosa.png", "filename": "a.png",
                                                "contentType": "image/png", "size": 10})
    assert r.status_code == 400


def test_presign_validates(client):
    r = client.post("/api/files/presign", json={"filename": "a.exe", "contentType": "application/x-msdownload",
                                                "size": 10})
    assert r.status_code == 400
    r = client.post("/api/files/presign", json={"filename": "a.png", "contentType": "image/png",
                                                "size": 5 * 1024 * 1024})
    assert r.status_code == 413


def test_storage_unavailable_maps_to_503(client, storage):
    storage.fail = True
    r = client.post("/api/files", files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 503 and "caído" not in r.text


def test_key_generator():
    from app.storage.keys import generate_key

    k = generate_key("Mis Fotos/../x", "image/webp", datetime(2026, 3, 9, tzinfo=timezone.utc))
    assert k.startswith("mis-fotos/x/2026/03/") and k.endswith(".webp")
    assert len(k.rsplit("/", 1)[1]) == len("0" * 32 + ".webp")
