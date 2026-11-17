"""API + worker de extremo a extremo con el traductor falso."""
import os

import pytest

from .conftest import OUT


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from app.main import app

    from .conftest import admin_client

    return admin_client(app)


def test_upload_validations(client, sample_pdf):
    r = client.post("/api/jobs", files={"file": ("x.pdf", b"not a pdf", "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 400 and "PDF" in r.json()["detail"]
    r = client.post("/api/jobs", files={"file": ("x.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "false"})
    assert r.status_code == 400


def test_upload_too_large_is_413(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    r = client.post("/api/jobs", files={"file": ("x.pdf", b"%PDF" + b"0" * (1024 * 1024), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 413 and "1 MB" in r.json()["detail"]


def test_direct_uploads_run_in_threadpool():
    """Las subidas directas son `def`: PyMuPDF, SHA-256, disco, BD y boto3 no bloquean el event loop (#06)."""
    import inspect

    from app.api.routes_files import upload_file
    from app.api.routes_jobs import create_job

    assert not inspect.iscoroutinefunction(create_job)
    assert not inspect.iscoroutinefunction(upload_file)


def test_upload_process_download(client, sample_pdf):
    from app import worker

    r = client.post("/api/jobs", files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    assert r.json()["status"] == "queued"

    claimed = worker.claim_job()
    assert claimed == job_id
    worker.process(job_id)

    st = client.get(f"/api/jobs/{job_id}").json()
    assert st["status"] == "done", st
    assert st["progress"] == 100
    assert all(s["state"] == "completed" for s in st["stages"])
    assert st["output_name"].endswith("(ES).pdf")

    pdf = client.get(f"/api/jobs/{job_id}/download")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    rep = client.get(f"/api/jobs/{job_id}/report").json()
    assert rep["validaciones"]["mismo_numero_de_paginas"]
    img = client.get(f"/api/jobs/{job_id}/pages/1/preview?version=original")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    (OUT / "api_download.pdf").write_bytes(pdf.content)


# ---- #12: los PDF de la API y las sesiones de la caché del worker se cierran

def test_worker_and_preview_close_resources(client, sample_pdf, monkeypatch):
    import gc

    import pymupdf

    from app import worker
    from app.db.session import engine

    r = client.post("/api/jobs", files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    assert worker.claim_job() == job_id
    gc.disable()  # sin el recolector, una sesión sin cerrar seguiría con su conexión prestada
    try:
        before = engine.pool.checkedout()
        worker.process(job_id)
        assert engine.pool.checkedout() == before
    finally:
        gc.enable()
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"

    opened = []
    real_open = pymupdf.open

    def spy(*a, **kw):
        opened.append(real_open(*a, **kw))
        return opened[-1]

    monkeypatch.setattr(pymupdf, "open", spy)
    assert client.get(f"/api/jobs/{job_id}/pages/1/preview").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/pages/999/preview?version=original").status_code == 404
    r = client.post("/api/jobs", files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    assert len(opened) == 3 and all(d.is_closed for d in opened)


# ---- #04: el estado de un trabajo no carga todas sus páginas y el listado no hace N+1

def _job_with_pages(owner_id: int, reviews: dict[int, list[str]], n_pages: int = 6) -> int:
    """Trabajo con `n_pages` páginas creadas en orden no correlativo; `reviews` = {número: motivos} a revisar."""
    from app.db.models import Document, Job, Page
    from app.db.session import session_scope

    with session_scope() as db:
        d = Document(original_name="libro-04.pdf", path="/nope/libro-04.pdf", sha256="0" * 64, page_count=n_pages,
                     title_es="Libro 04")
        j = Job(document=d, owner_id=owner_id, status="running", stage="translate", progress=40.0, current_page=3,
                options={"mode": "translate"})
        db.add(j)
        for number in [3, 1, *range(4, n_pages + 1), 2][:n_pages]:
            db.add(Page(job=j, number=number, width=420, height=595, kind="digital", needs_review=number in reviews, review_reasons=reviews.get(number, [])))
        db.flush()
        return j.id


def _page_queries(statements: list[str]) -> list[str]:
    return [s for s in statements if "FROM pages" in s]


def test_job_status_queries_only_pages_to_review(client):
    """`GET /api/jobs/{id}` hace ≤ 5 queries y la de páginas filtra `needs_review` (no trae el libro entero)."""
    from .conftest import auth_client, count_queries

    user_client = auth_client(client.app, "user")
    job_id = _job_with_pages(user_client.user.id, {3: ["ocr"], 5: ["longitud", "glosario"]})
    with count_queries() as q:
        r = user_client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200, r.text
    assert q.count <= 5, q.statements
    pages = _page_queries(q.statements)
    assert len(pages) == 1 and "needs_review" in pages[0], pages
    assert "pages.width" not in pages[0] and "pages.kind" not in pages[0], pages[0]  # solo number y motivos


def test_list_jobs_queries_do_not_grow_with_jobs(client):
    """`GET /api/jobs` con 10 trabajos hace ≤ 6 queries, las mismas que con 1."""
    from .conftest import auth_client, count_queries

    user_client = auth_client(client.app, "user")
    _job_with_pages(user_client.user.id, {2: ["ocr"]})
    with count_queries() as one:
        assert len(user_client.get("/api/jobs").json()) == 1
    for _ in range(9):
        _job_with_pages(user_client.user.id, {1: ["ocr"], 4: ["longitud"]})
    with count_queries() as ten:
        r = user_client.get("/api/jobs")
    assert r.status_code == 200 and len(r.json()) == 10
    assert ten.count <= 6, ten.statements
    assert ten.count == one.count, ten.statements


def test_job_status_json_unchanged(client):
    """El JSON de `GET /api/jobs/{id}` (y su entrada en `GET /api/jobs`) es el de antes, incluida `review_pages`
    en el orden de la relación `Job.pages`."""
    from .conftest import auth_client

    user_client = auth_client(client.app, "user")
    job_id = _job_with_pages(user_client.user.id, {3: ["ocr"], 1: [], 5: ["longitud", "glosario"]})
    st = user_client.get(f"/api/jobs/{job_id}").json()
    assert st == {
        "id": job_id, "mode": "translate", "ocr_lang": None, "status": "running", "stage": "translate",
        "progress": 40.0, "current_page": 3, "page_count": 6, "document_id": st["document_id"],
        "original_name": "libro-04.pdf", "title_es": "Libro 04", "output_name": None, "error": None,
        "recomposing": False, "recompose_error": None,
        "stages": [{"key": k, "label": label, "state": state} for (k, label), state in zip(
            [("upload", "Carga"), ("analyze", "Análisis"), ("ocr", "OCR"), ("protect", "Protección"),
             ("glossary", "Glosario"), ("translate", "Traducción"), ("rebuild", "Maquetación"),
             ("validate", "Validación"), ("done", "Descarga")],
            ["completed"] * 5 + ["in_progress"] + ["pending"] * 3, strict=True)],
        "review_pages": [{"page": 3, "reasons": ["ocr"]}, {"page": 1, "reasons": []},
                         {"page": 5, "reasons": ["longitud", "glosario"]}],
    }
    assert [j for j in user_client.get("/api/jobs").json() if j["id"] == job_id] == [st]


def _fake_epub_job(tmp_path, job_id: int):
    """Trabajo mínimo para _epub_for: solo hace falta id y un PDF de salida existente."""
    from types import SimpleNamespace

    pdf = tmp_path / f"job{job_id}.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return SimpleNamespace(id=job_id, output_path=str(pdf))


def test_concurrent_epub_downloads_build_once(tmp_path, monkeypatch):
    import threading
    import time

    from app.api import routes_jobs
    from app.pipeline.epub import epub_path_for

    calls = []

    def fake_build(db, job):
        calls.append(job.id)
        time.sleep(0.2)  # sin lock, la segunda descarga también vería que falta el archivo
        epub_path_for(job.output_path).write_bytes(b"epub")

    monkeypatch.setattr(routes_jobs, "build_epub_for_job", fake_build)
    job = _fake_epub_job(tmp_path, 900001)
    start = threading.Barrier(2)
    paths = []

    def download():
        start.wait()
        paths.append(routes_jobs._epub_for(None, job))

    ts = [threading.Thread(target=download) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert calls == [job.id] and len(paths) == 2 and paths[0].read_bytes() == b"epub"


def test_epub_locks_do_not_grow_with_jobs(tmp_path, monkeypatch):
    from app.api import routes_jobs
    from app.pipeline.epub import epub_path_for

    monkeypatch.setattr(routes_jobs, "build_epub_for_job",
                        lambda db, job: epub_path_for(job.output_path).write_bytes(b"epub"))
    before = len(routes_jobs._build_locks)
    for i in range(100):
        routes_jobs._epub_for(None, _fake_epub_job(tmp_path, 910000 + i))
    assert len(routes_jobs._build_locks) <= max(before, 1)
    # mientras una descarga retiene el lock, las demás del mismo trabajo reciben el mismo
    lock = routes_jobs._build_lock("epub", 1)
    assert routes_jobs._build_lock("epub", 1) is lock and routes_jobs._build_lock("azw3", 1) is not lock
