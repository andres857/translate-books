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
    for i, (a, b) in enumerate(zip(before, after, strict=True), 1):
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
    assert client.get(f"/api/jobs/{job_id}/download?format=mobi").status_code == 422


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


# ---- #05: el resumen agrega los bloques en una consulta (antes, una por página)

@pytest.fixture
def extra_pages(job_id):
    """Añade al trabajo 20 páginas con bloques de borde (sin bloques, escala 0 o NULL, traducción vacía,
    editados, acciones distintas de «translate») y las borra al terminar."""
    from sqlalchemy import select

    from app.db.models import Page, Segment
    from app.db.session import SessionLocal

    first = 1000
    with SessionLocal() as s:
        for i in range(20):
            page = Page(job_id=job_id, number=first + i, width=100, height=100, kind="digital",
                        needs_review=i % 3 == 0, review_reasons=["prueba"] if i % 3 == 0 else [])
            for j in range(i % 4):  # la primera página queda sin bloques
                page.segments.append(Segment(
                    seg_key=f"x{i}_{j}", bbox=[0, 0, 1, 1], source_text="a", source_html="a",
                    action=("translate", "keep", "translate", "review")[j],
                    translation=(None, "b", "", "c")[j], edited=j == 1,
                    fit_scale=(None, 0.0, 0.876, 0.5 + i / 100)[j]))
            s.add(page)
        s.commit()
    yield
    with SessionLocal() as s:
        for page in s.scalars(select(Page).where(Page.job_id == job_id, Page.number >= first)):
            s.delete(page)
        s.commit()


def test_summary_queries_do_not_grow_with_pages(client, job_id, request):
    from .conftest import count_queries

    with count_queries() as before:
        n_before = len(client.get(f"/api/admin/jobs/{job_id}/summary").json()["pages"])
    request.getfixturevalue("extra_pages")
    with count_queries() as after:
        n_after = len(client.get(f"/api/admin/jobs/{job_id}/summary").json()["pages"])
    assert n_after == n_before + 20
    assert after.count == before.count <= 8, after.statements
    assert sum("FROM segments" in st for st in after.statements) == 1


def test_summary_totals_match_per_page_computation(client, job_id, extra_pages):
    """Los totales por página son los que calculaba el código anterior recorriendo `page.segments`."""
    from sqlalchemy import select

    from app.db.models import Page
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        expected = []
        for p in s.scalars(select(Page).where(Page.job_id == job_id).order_by(Page.number)):
            scales = [g.fit_scale for g in p.segments if g.fit_scale]
            expected.append({"number": p.number, "kind": p.kind, "needs_review": p.needs_review,
                             "reasons": p.review_reasons or [], "segments": len(p.segments),
                             "translated": sum(1 for g in p.segments if g.action == "translate" and g.translation),
                             "edited": sum(1 for g in p.segments if g.edited),
                             "min_scale": round(min(scales), 2) if scales else None})
    s = client.get(f"/api/admin/jobs/{job_id}/summary").json()
    assert s["pages"] == expected
    assert any(p["segments"] == 0 and p["min_scale"] is None for p in s["pages"])
    assert s["totals"]["segments"] == sum(p["segments"] for p in expected)
    assert s["totals"]["edited"] == sum(p["edited"] for p in expected)
    assert s["totals"]["pages"] == len(expected)
    assert s["totals"]["review"] == sum(p["needs_review"] for p in expected)


# ---- #10: índices únicos contra duplicados en glosario, términos y bloques

def _no_db_text(r) -> None:
    body = r.text.lower()
    assert r.json()["detail"] == "Ese término ya existe."
    assert not any(t in body for t in ("unique", "constraint", "sqlite", "integrity", "glossary", "protected_terms"))


@pytest.mark.parametrize("scope", ["global", "book"])
def test_glossary_duplicate_is_409(client, job_id, scope):
    from sqlalchemy import func, select

    from app.db.models import GlossaryEntry
    from app.db.session import SessionLocal

    doc_id = client.get(f"/api/jobs/{job_id}").json()["document_id"] if scope == "book" else None
    first = client.post("/api/glossary", json={"source": "Ascendant", "target": "Ascendente", "document_id": doc_id})
    assert first.status_code == 200, first.text
    dup = client.post("/api/glossary", json={"source": " ascendant ", "target": "Otro", "document_id": doc_id})
    assert dup.status_code == 409
    _no_db_text(dup)
    with SessionLocal() as s:
        n = s.scalar(select(func.count(GlossaryEntry.id)).where(
            func.lower(GlossaryEntry.source) == "ascendant", GlossaryEntry.document_id.is_(doc_id)
            if doc_id is None else GlossaryEntry.document_id == doc_id))
    assert n == 1
    client.delete(f"/api/glossary/{first.json()['id']}")


def test_glossary_same_term_global_and_per_book_is_allowed(client, job_id):
    doc_id = client.get(f"/api/jobs/{job_id}").json()["document_id"]
    a = client.post("/api/glossary", json={"source": "Midheaven", "target": "Medio cielo"})
    b = client.post("/api/glossary", json={"source": "Midheaven", "target": "MC", "document_id": doc_id})
    assert a.status_code == b.status_code == 200
    for r in (a, b):
        client.delete(f"/api/glossary/{r.json()['id']}")


@pytest.mark.parametrize("scope", ["global", "book"])
def test_protected_term_duplicate_is_409(client, job_id, scope):
    from sqlalchemy import func, select

    from app.db.models import ProtectedTerm
    from app.db.session import SessionLocal

    doc_id = client.get(f"/api/jobs/{job_id}").json()["document_id"] if scope == "book" else None
    first = client.post("/api/protected-terms", json={"term": "Chiron", "document_id": doc_id})
    assert first.status_code == 200, first.text
    dup = client.post("/api/protected-terms", json={"term": " Chiron ", "category": "term", "document_id": doc_id})
    assert dup.status_code == 409
    _no_db_text(dup)
    with SessionLocal() as s:
        n = s.scalar(select(func.count(ProtectedTerm.id)).where(
            ProtectedTerm.term == "Chiron", ProtectedTerm.document_id.is_(doc_id)
            if doc_id is None else ProtectedTerm.document_id == doc_id))
    assert n == 1
    client.delete(f"/api/protected-terms/{first.json()['id']}")


def test_duplicate_seg_key_in_page_raises_integrity_error(client, job_id):
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db.models import Page, Segment
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        page_id = s.scalar(select(Page.id).where(Page.job_id == job_id, Page.number == 1))
        for _ in range(2):
            s.add(Segment(page_id=page_id, seg_key="dup_s001", bbox=[0, 0, 1, 1], source_text="a", source_html="a"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        assert s.scalar(select(Segment.id).where(Segment.seg_key == "dup_s001")) is None


# ---- #09: borrar un trabajo no carga sus páginas ni sus bloques (ON DELETE CASCADE en la BD)

def _processed_job(client, sample_pdf) -> int:
    from app import worker

    r = client.post("/api/jobs", files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    while (claimed := worker.claim_job()) is not None:
        worker.process(claimed)
    return r.json()["id"]


def _rows_of(job_id: int) -> tuple[int, int]:
    from sqlalchemy import func, select

    from app.db.models import Page, Segment
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        pages = s.scalar(select(func.count(Page.id)).where(Page.job_id == job_id))
        segs = s.scalar(select(func.count(Segment.id)).join(Page).where(Page.job_id == job_id))
    return pages, segs


def test_delete_job_queries_do_not_grow_with_segments(client, sample_pdf):
    from app.db.models import Page, Segment
    from app.db.session import SessionLocal

    from .conftest import count_queries

    small, big = _processed_job(client, sample_pdf), _processed_job(client, sample_pdf)
    with SessionLocal() as s:  # el segundo, con 20 páginas y 200 bloques más
        for i in range(20):
            s.add(Page(job_id=big, number=1000 + i, width=100, height=100, kind="digital", segments=[
                Segment(seg_key=f"x{i}_{j}", bbox=[0, 0, 1, 1], source_text="a", source_html="a") for j in range(10)]))
        s.commit()
    small_rows, big_rows = _rows_of(small), _rows_of(big)
    assert small_rows[1] > 0 and big_rows == (small_rows[0] + 20, small_rows[1] + 200)

    with count_queries() as q_small:
        assert client.delete(f"/api/jobs/{small}").status_code == 200
    with count_queries() as q_big:
        assert client.delete(f"/api/jobs/{big}").status_code == 200
    assert q_big.count == q_small.count <= 25, q_big.statements
    assert not any(st.lstrip().upper().startswith(("DELETE FROM PAGES", "DELETE FROM SEGMENTS"))
                   for st in q_big.statements), q_big.statements
    assert _rows_of(small) == _rows_of(big) == (0, 0)


def test_delete_job_queries_do_not_grow_with_glossary_or_attempts(client, sample_pdf):
    """#20: glosario, términos e intentos se borran con un DELETE en bloque, no fila a fila."""
    from sqlalchemy import func, select

    from app import playground as pg
    from app.db.models import GlossaryEntry, Job, PlaygroundAttempt, PlaygroundRun, ProtectedTerm
    from app.db.session import SessionLocal

    from .conftest import count_queries

    def prepare(job_id: int, entries: int, attempts: int) -> tuple[int, list]:
        with SessionLocal() as s:
            doc_id = s.get(Job, job_id).document_id
            for i in range(entries):
                s.add(GlossaryEntry(source=f"term{i}", target=f"término{i}", document_id=doc_id))
                s.add(ProtectedTerm(term=f"Name{i}", document_id=doc_id))
            run = PlaygroundRun(job_id=job_id, task="translate", pages="1", variants=[], status="done", results=[])
            s.add(run)
            s.flush()
            pdfs = []
            for i in range(attempts):
                pdf = pg.attempts_dir(run.id) / f"{i}.pdf"
                pdf.parent.mkdir(parents=True, exist_ok=True)
                pdf.write_bytes(b"%PDF-1.4")
                pdfs.append(pdf)
                s.add(PlaygroundAttempt(run_id=run.id, job_id=job_id, label="A", kind="try", pages="1", pdf=str(pdf)))
            s.commit()
            return doc_id, pdfs

    def leftovers(job_id: int, doc_id: int) -> tuple[int, int, int, int]:
        with SessionLocal() as s:
            return tuple(s.scalar(select(func.count()).select_from(m).where(cond)) for m, cond in (
                (GlossaryEntry, GlossaryEntry.document_id == doc_id),
                (ProtectedTerm, ProtectedTerm.document_id == doc_id),
                (PlaygroundAttempt, PlaygroundAttempt.job_id == job_id),
                (PlaygroundRun, PlaygroundRun.job_id == job_id)))

    small, big = _processed_job(client, sample_pdf), _processed_job(client, sample_pdf)
    small_doc, small_pdfs = prepare(small, entries=1, attempts=0)
    big_doc, big_pdfs = prepare(big, entries=50, attempts=5)
    assert leftovers(big, big_doc) == (50, 50, 5, 1) and all(p.exists() for p in big_pdfs)

    with count_queries() as q_small:
        assert client.delete(f"/api/jobs/{small}").status_code == 200
    with count_queries() as q_big:
        assert client.delete(f"/api/jobs/{big}").status_code == 200
    assert q_big.count == q_small.count, q_big.statements
    # ni SELECT de filas ni DELETE por id (el ORM los agrupa en un executemany que count_queries cuenta como uno)
    flat = [" ".join(st.split()) for st in q_big.statements]
    for table, col in (("glossary", "document_id"), ("protected_terms", "document_id"), ("playground_attempts", "job_id")):
        assert [st for st in flat if f" {table}" in st and not st.startswith(f"SELECT {table}.pdf ")] == [
            f"DELETE FROM {table} WHERE {table}.{col} = ?"], flat
    assert leftovers(small, small_doc) == leftovers(big, big_doc) == (0, 0, 0, 0)
    assert not small_pdfs and not any(p.exists() for p in big_pdfs)


def test_protected_term_category_must_be_known(client):
    """#11: la categoría es una de las que pinta la vista de términos (en mayúsculas o minúsculas)."""
    bad = client.post("/api/protected-terms", json={"term": "Sol", "category": "cualquier-cosa-larguísima"})
    assert bad.status_code == 422
    assert bad.json()["errors"] == [{"loc": ["body", "category"], "type": "literal_error"}]
    assert "larguísima" not in bad.text
    for cat, stored in (("BRAND", "BRAND"), ("code", "CODE")):
        ok = client.post("/api/protected-terms", json={"term": f"Sol {cat}", "category": cat})
        assert ok.status_code == 200, ok.text
        row = next(t for t in client.get("/api/protected-terms").json() if t["id"] == ok.json()["id"])
        assert row["category"] == stored
        client.delete(f"/api/protected-terms/{ok.json()['id']}")


def test_download_format_and_preview_version_are_closed_lists(client, job_id):
    """#11: formato y versión desconocidos → 422 sin eco del valor (antes: 400 y la traducción, respectivamente)."""
    r = client.get(f"/api/jobs/{job_id}/download?format=docx")
    assert r.status_code == 422
    assert r.json()["errors"] == [{"loc": ["query", "format"], "type": "literal_error"}] and "docx" not in r.text
    r = client.get(f"/api/jobs/{job_id}/pages/1/preview?version=otra")
    assert r.status_code == 422
    assert r.json()["errors"] == [{"loc": ["query", "version"], "type": "literal_error"}] and "otra" not in r.text
    assert client.get(f"/api/jobs/{job_id}/pages/1/preview?version=translated").status_code == 200


def test_upload_mode_and_ocr_lang_are_closed_lists(client, sample_pdf):
    """#11: modo e idioma de OCR los valida FastAPI (422 sin eco) en vez de la función, y no se crea nada."""
    before = len(client.get("/api/jobs").json())
    for bad, field in (({"mode": "otro"}, "mode"), ({"mode": "digitize", "ocr_lang": "klingon"}, "ocr_lang")):
        r = client.post("/api/jobs", files={"file": ("s.pdf", sample_pdf.read_bytes(), "application/pdf")},
                        data={"rights_confirmed": "true", **bad})
        assert r.status_code == 422, r.text
        assert r.json()["errors"] == [{"loc": ["body", field], "type": "literal_error"}]
        assert "otro" not in r.text and "klingon" not in r.text
    assert len(client.get("/api/jobs").json()) == before
