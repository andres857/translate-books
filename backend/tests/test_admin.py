"""Admin: resumen, bloques, corrección manual, recomposición de una página y AZW3 (traductor falso)."""
import os

import pymupdf
import pytest

from app.pipeline.azw3 import ebook_convert_available


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data_admin"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from app.main import app

    from .conftest import admin_client

    return admin_client(app)


@pytest.fixture(scope="module")
def job_id(client, sample_pdf):
    from app import worker

    r = client.post("/api/jobs", files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    while (claimed := worker.claim_job()) is not None:  # puede haber trabajos de otros módulos en la cola
        worker.process(claimed)
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "done"
    return jid


def _page_texts(pdf_bytes: bytes) -> list[str]:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [p.get_text() for p in doc]


def test_summary(client, job_id):
    s = client.get(f"/api/admin/jobs/{job_id}/summary").json()
    assert s["job"]["id"] == job_id
    assert s["totals"]["pages"] == s["job"]["page_count"] == len(s["pages"])
    assert s["totals"]["ok"] + s["totals"]["review"] == s["totals"]["pages"]
    assert "mismo_numero_de_paginas" in s["checks"]
    assert s["stats"]["segmentos_a_traducir"] > 0
    assert [p["number"] for p in s["pages"]] == list(range(1, len(s["pages"]) + 1))
    assert client.get("/api/admin/jobs/99999/summary").status_code == 404


def test_segments(client, job_id):
    page = client.get(f"/api/admin/jobs/{job_id}/pages/1/segments").json()
    assert page["number"] == 1 and page["width"] > 0
    seg = next(s for s in page["segments"] if s["action"] == "translate")
    assert seg["source_html"] and seg["translation"] and seg["edited"] is False and len(seg["bbox"]) == 4
    assert client.get(f"/api/admin/jobs/{job_id}/pages/999/segments").status_code == 404


def test_edit_and_recompose_only_that_page(client, job_id):
    from app import worker

    before = _page_texts(client.get(f"/api/jobs/{job_id}/download").content)
    number = 4
    page = client.get(f"/api/admin/jobs/{job_id}/pages/{number}/segments").json()
    seg = max((s for s in page["segments"] if s["action"] == "translate"), key=lambda s: len(s["source_html"]))

    assert client.put(f"/api/admin/jobs/{job_id}/segments/{seg['key']}", json={"translation": "  "}).status_code in (400, 422)
    r = client.put(f"/api/admin/jobs/{job_id}/segments/{seg['key']}",
                   json={"translation": "Texto corregido a mano <b>ZQXJ</b><script>x</script>"})
    assert r.status_code == 200, r.text
    assert r.json()["edited"] is True and "<script>" not in r.json()["translation"]

    r = client.post(f"/api/admin/jobs/{job_id}/pages/{number}/recompose")
    assert r.status_code == 200 and r.json()["status"] == "queued" and r.json()["recomposing"] is True
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 409
    assert worker.claim_job() == job_id
    worker.process(job_id)

    st = client.get(f"/api/jobs/{job_id}").json()
    assert st["status"] == "done" and st["recomposing"] is False and st["recompose_error"] is None
    after = _page_texts(client.get(f"/api/jobs/{job_id}/download").content)
    assert len(after) == len(before)
    assert "ZQXJ" in after[number - 1] and "ZQXJ" not in before[number - 1]
    for i, (a, b) in enumerate(zip(before, after), 1):
        if i != number:
            assert a == b, f"la página {i} no debía cambiar"
    # la corrección sigue guardada y el resto de bloques de la página conserva su traducción
    again = client.get(f"/api/admin/jobs/{job_id}/pages/{number}/segments").json()
    kept = {s["key"]: s for s in again["segments"]}
    assert kept[seg["key"]]["edited"] is True and "ZQXJ" in kept[seg["key"]]["translation"]
    assert len(again["segments"]) == len(page["segments"])
    for s in page["segments"]:
        if s["key"] != seg["key"]:
            assert kept[s["key"]]["translation"] == s["translation"]
    s2 = client.get(f"/api/admin/jobs/{job_id}/summary").json()
    assert s2["totals"]["edited"] == 1 and len(s2["pages"]) == len(before)
    # el EPUB para Kindle se regenera con la corrección
    import io
    import zipfile

    epub = client.get(f"/api/jobs/{job_id}/download?format=epub")
    assert epub.status_code == 200
    with zipfile.ZipFile(io.BytesIO(epub.content)) as z:
        assert any(b"ZQXJ" in z.read(n) for n in z.namelist() if n.endswith(".xhtml"))


def test_recompose_requires_finished_book(client, job_id):
    assert client.post(f"/api/admin/jobs/{job_id}/pages/999/recompose").status_code == 404


def test_terms_filter(client, job_id, sample_pdf):
    doc_id = client.get(f"/api/jobs/{job_id}").json()["document_id"]
    other = client.post("/api/jobs", files={"file": ("otro.pdf", sample_pdf.read_bytes(), "application/pdf")},
                        data={"rights_confirmed": "true"}).json()
    client.post(f"/api/jobs/{other['id']}/cancel")
    assert client.post("/api/glossary", json={"source": "x", "target": "y", "document_id": 999999}).status_code == 400
    a = client.post("/api/glossary", json={"source": "birth chart", "target": "carta natal"}).json()["id"]
    b = client.post("/api/glossary", json={"source": "house", "target": "casa", "document_id": doc_id}).json()["id"]
    c = client.post("/api/glossary", json={"source": "other", "target": "otro", "document_id": other["document_id"]}).json()["id"]
    ids = {g["id"] for g in client.get(f"/api/glossary?document_id={doc_id}").json()}
    assert {a, b} <= ids and c not in ids
    assert c in {g["id"] for g in client.get("/api/glossary").json()}
    for i in (a, b, c):
        client.delete(f"/api/glossary/{i}")


def test_azw3_download(client, job_id, monkeypatch):
    if not ebook_convert_available():
        pytest.skip("Calibre (ebook-convert) no está instalado: no se prueba la conversión real a AZW3")
    assert client.get("/api/health").json()["azw3_available"] is True
    r = client.get(f"/api/jobs/{job_id}/download?format=azw3")
    assert r.status_code == 200, r.text
    assert r.content[60:68] == b"BOOKMOBI" and len(r.content) > 2000
    assert client.get(f"/api/jobs/{job_id}/download?format=epub").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/download?format=mobi").status_code == 400


def test_azw3_without_calibre(client, job_id, monkeypatch):
    monkeypatch.setenv("EBOOK_CONVERT_BIN", "no-existe-ebook-convert")
    assert client.get("/api/health").json()["azw3_available"] is False
    r = client.get(f"/api/jobs/{job_id}/download?format=azw3")
    assert r.status_code == 409 and "Calibre" in r.json()["detail"]
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 200


def _seg_row(job_id: int, key: str):
    from sqlalchemy import select

    from app.db.models import Page, Segment
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        seg = s.scalars(select(Segment).join(Page).where(Page.job_id == job_id, Segment.seg_key == key)).one()
        return seg.translation, bool(seg.edited)


def _set_status(job_id: int, status: str) -> None:
    from app.db.models import Job
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        s.get(Job, job_id).status = status
        s.commit()


def test_edit_rejected_while_processing(client, job_id):
    """#01: con el trabajo en cola o en marcha, la corrección se rechaza (409) y el bloque no cambia."""
    page = client.get(f"/api/admin/jobs/{job_id}/pages/5/segments").json()
    seg = next(s for s in page["segments"] if s["action"] == "translate")
    before = _seg_row(job_id, seg["key"])
    try:
        for status in ("queued", "running"):
            _set_status(job_id, status)
            r = client.put(f"/api/admin/jobs/{job_id}/segments/{seg['key']}", json={"translation": "No debe quedar"})
            assert r.status_code == 409, (status, r.text)
            assert "procesando" in r.json()["detail"]
            assert _seg_row(job_id, seg["key"]) == before
    finally:
        _set_status(job_id, "done")
    # con el trabajo terminado, se guarda como siempre
    r = client.put(f"/api/admin/jobs/{job_id}/segments/{seg['key']}", json={"translation": "Corregido WQPZ"})
    assert r.status_code == 200, r.text
    assert r.json()["edited"] is True
    assert _seg_row(job_id, seg["key"]) == ("Corregido WQPZ", True)


def test_edit_during_queued_recompose_keeps_first_correction(client, job_id):
    """#01: editar → recomponer → editar otro bloque de la misma página en cola se rechaza;
    tras el worker la primera corrección sigue."""
    from app import worker

    number = 3
    page = client.get(f"/api/admin/jobs/{job_id}/pages/{number}/segments").json()
    segs = [s for s in page["segments"] if s["action"] == "translate"]
    assert len(segs) >= 2
    first, second = segs[0], segs[1]
    r = client.put(f"/api/admin/jobs/{job_id}/segments/{first['key']}", json={"translation": "Primera KVJX"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/admin/jobs/{job_id}/pages/{number}/recompose")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    second_before = _seg_row(job_id, second["key"])
    r = client.put(f"/api/admin/jobs/{job_id}/segments/{second['key']}", json={"translation": "Segunda perdida"})
    assert r.status_code == 409, r.text
    assert _seg_row(job_id, second["key"]) == second_before
    assert worker.claim_job() == job_id
    worker.process(job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"
    kept = {s["key"]: s for s in client.get(f"/api/admin/jobs/{job_id}/pages/{number}/segments").json()["segments"]}
    assert kept[first["key"]]["edited"] is True and kept[first["key"]]["translation"] == "Primera KVJX"
    assert kept[second["key"]]["edited"] is False


def _job_options(job_id: int) -> dict:
    from app.db.models import Job
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        return dict(s.get(Job, job_id).options or {})


def test_second_recompose_rejected_while_recomposing(client, job_id):
    """#03: con una recomposición en cola o en marcha, pedir otra página da 409 y la primera sigue pedida."""
    from app import worker

    r = client.post(f"/api/admin/jobs/{job_id}/pages/3/recompose")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    r = client.post(f"/api/admin/jobs/{job_id}/pages/5/recompose")
    assert r.status_code == 409, r.text
    assert "Ya se está recomponiendo" in r.json()["detail"]
    assert _job_options(job_id)["recompose"] == [3]
    assert worker.claim_job() == job_id  # running
    r = client.post(f"/api/admin/jobs/{job_id}/pages/5/recompose")
    assert r.status_code == 409 and "Ya se está recomponiendo" in r.json()["detail"]
    assert _job_options(job_id)["recompose"] == [3]
    worker.process(job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"
    # terminada la primera, la segunda ya se acepta
    r = client.post(f"/api/admin/jobs/{job_id}/pages/5/recompose")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert worker.claim_job() == job_id
    worker.process(job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"


def test_concurrent_recompose_loses_nothing(client, job_id, monkeypatch):
    """#03: si otra petición encola entre la lectura y la escritura, esta da 409 y no pisa la otra."""
    from app import worker
    from app.api import routes_admin
    from app.db.models import Job
    from app.db.session import SessionLocal

    real = routes_admin._page_or_404

    def other_request_wins(db, jid, number):
        with SessionLocal() as s:  # la otra petición ya encoló la página 3
            job = s.get(Job, jid)
            job.options = {**(job.options or {}), "recompose": [3]}
            job.status = "queued"
            s.commit()
        return real(db, jid, number)

    monkeypatch.setattr(routes_admin, "_page_or_404", other_request_wins)
    r = client.post(f"/api/admin/jobs/{job_id}/pages/5/recompose")
    assert r.status_code == 409 and "Ya se está recomponiendo" in r.json()["detail"]
    assert _job_options(job_id)["recompose"] == [3]
    monkeypatch.setattr(routes_admin, "_page_or_404", real)
    assert worker.claim_job() == job_id
    worker.process(job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"


def test_recompose_clears_done_pages_and_previous_error(client, job_id, monkeypatch):
    """#03: tras recomponer, options no guarda las páginas hechas ni el recompose_error anterior."""
    from app import worker

    real = worker.recompose_page

    def broken(*args, **kwargs):
        raise RuntimeError("falla de prueba")

    monkeypatch.setattr(worker, "recompose_page", broken)
    assert client.post(f"/api/admin/jobs/{job_id}/pages/2/recompose").status_code == 200
    assert worker.claim_job() == job_id
    worker.process(job_id)
    st = client.get(f"/api/jobs/{job_id}").json()
    assert st["status"] == "done" and st["recompose_error"]
    assert "recompose" not in _job_options(job_id)

    monkeypatch.setattr(worker, "recompose_page", real)
    assert client.post(f"/api/admin/jobs/{job_id}/pages/2/recompose").status_code == 200
    assert worker.claim_job() == job_id
    worker.process(job_id)
    st = client.get(f"/api/jobs/{job_id}").json()
    assert st["status"] == "done" and st["recompose_error"] is None and st["recomposing"] is False
    options = _job_options(job_id)
    assert "recompose" not in options and "recompose_error" not in options
