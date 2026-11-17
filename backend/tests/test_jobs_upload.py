"""Subida de libros directa a S3: /api/jobs/presign + /api/jobs/from-upload (storage falso)."""
import os
from pathlib import Path

import pytest

from .test_files import FakeStorage


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from .conftest import admin_client

    from app.main import app
    from app.storage import get_storage

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield admin_client(app), fake
    app.dependency_overrides.pop(get_storage, None)


def _presign(client, size, name="libro.pdf"):
    return client.post("/api/jobs/presign", json={"filename": name, "size": size})


def _payload(key, **kw):
    return {"key": key, "filename": "Libro ñ.pdf", "rights_confirmed": True, "mode": "prepare", **kw}


def test_presign_validates(ctx):
    client, _ = ctx
    assert _presign(client, 10, "libro.epub").status_code == 400
    assert _presign(client, 10 ** 12).status_code == 413
    r = _presign(client, 1000)
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith("books/incoming/") and body["key"].endswith(".pdf")
    assert body["method"] == "PUT" and body["headers"] == {"Content-Type": "application/pdf"}


def test_from_upload_creates_job_and_removes_object(ctx, sample_pdf):
    client, storage = ctx
    data = sample_pdf.read_bytes()
    key = _presign(client, len(data)).json()["key"]
    storage.objects[key] = (data, "application/pdf")  # simula el PUT del navegador
    r = client.post("/api/jobs/from-upload", json=_payload(key))
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["mode"] == "prepare" and job["original_name"] == "Libro ñ.pdf" and job["status"] == "queued"
    assert key not in storage.objects
    from app.db.models import Document
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        path = Path(db.get(Document, job["document_id"]).path)
    assert path.read_bytes() == data


def test_from_upload_rejects_foreign_key(ctx):
    client, _ = ctx
    assert client.post("/api/jobs/from-upload", json=_payload("files/2026/01/x.pdf")).status_code == 400
    assert client.post("/api/jobs/from-upload", json=_payload("books/incoming/../x.pdf")).status_code == 400
    # la carpeta temporal de otro usuario tampoco vale
    assert client.post("/api/jobs/from-upload", json=_payload("books/incoming/u999999/2026/01/x.pdf")).status_code == 400


def test_from_upload_missing_object(ctx):
    client, _ = ctx
    r = client.post("/api/jobs/from-upload", json=_payload(f"books/incoming/u{client.user.id}/2026/01/nada.pdf"))
    assert r.status_code == 400 and "subido" in r.json()["detail"]


def test_from_upload_invalid_pdf_removes_object(ctx):
    client, storage = ctx
    key = _presign(client, 9).json()["key"]
    storage.objects[key] = (b"no es pdf", "application/pdf")
    r = client.post("/api/jobs/from-upload", json=_payload(key))
    assert r.status_code == 400 and key not in storage.objects


def test_from_upload_requires_rights(ctx, sample_pdf):
    client, storage = ctx
    data = sample_pdf.read_bytes()
    key = _presign(client, len(data)).json()["key"]
    storage.objects[key] = (data, "application/pdf")
    r = client.post("/api/jobs/from-upload", json=_payload(key, rights_confirmed=False))
    assert r.status_code == 400 and key not in storage.objects


def test_presign_storage_down_is_503(ctx):
    client, storage = ctx
    storage.fail = True
    try:
        # el FakeStorage solo falla en upload: forzamos el fallo en presign
        orig = storage.presigned_upload_url

        def boom(*a, **k):
            from app.storage.errors import StorageUnavailable

            raise StorageUnavailable("caído")

        storage.presigned_upload_url = boom
        r = _presign(client, 100)
        assert r.status_code == 503 and "caído" not in r.text
    finally:
        storage.fail = False
        storage.presigned_upload_url = orig
