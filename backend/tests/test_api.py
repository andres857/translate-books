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
