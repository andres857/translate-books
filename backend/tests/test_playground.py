"""Playground: variantes (método, modelo, prompt) sobre un capítulo ya procesado, sin tocar producción."""
import time

import pytest
from sqlalchemy import func, select

from app import playground as pg
from app import runtime_settings as rsmod
from app.pipeline.translate import FatalAPIError, UsageMeter


@pytest.fixture(scope="module")
def db():
    from app.cli import migrate

    migrate()
    from app.db.session import SessionLocal

    return SessionLocal


@pytest.fixture
def book(db):
    """Libro traducido con 3 páginas; el texto protegido guardado difiere del HTML a propósito."""
    from app.db.models import Document, Job, Page, Segment

    with db() as s:
        doc = Document(original_name="libro.pdf", path="/no/existe.pdf", sha256="x", page_count=3, title="Libro")
        job = Job(document=doc, status="done", options={})
        s.add(job)
        s.flush()
        for n in (1, 2, 3):
            page = Page(job_id=job.id, number=n, width=400, height=600, kind="digital")
            page.segments = [
                Segment(seg_key=f"p{n:03d}_s001", bbox=[0, 0, 10, 10], block_type="body", source_text=f"Text {n}",
                        source_html=f"Text {n} by Carole", protected_text=f"Text {n} by __NAME_001__",
                        placeholders={"__NAME_001__": "Carole"}, action="translate"),
                Segment(seg_key=f"p{n:03d}_s002", bbox=[0, 20, 10, 30], block_type="heading", source_text="42",
                        source_html="42", action="keep"),
            ]
            s.add(page)
        s.commit()
        return job.id


class Spy:
    def __init__(self, model="spy", fail=None):
        self.model, self.fail, self.prompts, self.meter, self.seen = model, fail, None, None, []

    def translate_batch(self, items, context):
        if self.fail:
            raise self.fail
        self.seen.extend(items)
        if self.meter:
            self.meter.add(10, 5, None)
        return {it["id"]: {"id": it["id"], "translation": "ES " + it["text"]} for it in items}

    def correct_batch(self, items, context):
        return {it["id"]: {"id": it["id"], "text": it["text"].replace("rn", "m")} for it in items}

    def extract_names(self, text):
        return []


def test_parse_pages():
    assert pg.parse_pages("2-3", 10) == [2, 3]
    assert pg.parse_pages(" 5 ", 10) == [5]
    assert pg.parse_pages("7, 3, 12-14, 3", 20) == [3, 7, 12, 13, 14]  # sueltas, rangos y duplicados
    assert pg.format_pages([3, 7, 12, 13, 14]) == "3,7,12-14"
    assert pg.format_pages(list(range(1, 313))) == "1-312"
    for bad in ("0-2", "3-2", "9-12", "a", "", "1,,2", "1-2-3"):
        with pytest.raises(ValueError):
            pg.parse_pages(bad, 10)


def test_scope_limits():
    assert pg.scope_pages("book", "", 312) == list(range(1, 313))  # libro entero: sin límite
    assert pg.scope_pages("page", "4", 10) == [4]
    with pytest.raises(ValueError):
        pg.scope_pages("page", "4-5", 10)  # una página es una sola
    with pytest.raises(ValueError):
        pg.scope_pages("pages", f"1-{pg.MAX_PAGES + 1}", 500)
    assert len(pg.scope_pages("chapter", "1-150", 500)) == 150  # un capítulo largo no se recorta
    with pytest.raises(ValueError):
        pg.scope_pages("todo", "1", 10)


def test_validate_variants():
    v = pg.validate_variants([{"provider": "deepseek", "model": "deepseek-pro", "thinking": "high"}], "translate", {})
    assert v[0]["label"] == "A" and v[0]["prompt"] == "production" and v[0]["prompt_text"] is None
    assert v[0]["model"] == "deepseek-pro" and v[0]["thinking"] == "high"
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "fake"}] * 5, "translate", {})
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "gpt"}], "translate", {})
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "claude"}], "translate", {})  # modo retirado
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "deepseek", "thinking": "extremo"}], "translate", {})
    with pytest.raises(ValueError):  # borrador de otra tarea
        pg.validate_variants([{"provider": "fake", "prompt": 7}], "translate", {7: ("correct", "x")})
    v = pg.validate_variants([{"provider": "fake", "prompt": 7}], "translate", {7: ("translate", "MI PROMPT")})
    assert v[0]["prompt_text"] == "MI PROMPT"  # se copia al lanzar


def test_run_uses_stored_protection_and_isolated_cache(db, book, monkeypatch):
    from app.db.models import PlaygroundRun, TranslationCache

    spies = {}

    def factory(rs, prompts=None):
        spy = Spy(model=f"spy-{rs.provider}")
        spy.prompts = prompts
        spies[rs.provider] = spy
        return spy

    monkeypatch.setattr(rsmod, "make_translator", factory)
    with db() as s:
        before = s.scalar(select(func.count()).select_from(TranslationCache))
        variants = pg.validate_variants([{"provider": "fake"}, {"provider": "deepseek", "model": "m",
                                          "prompt": 1}], "translate", {1: ("translate", "BORRADOR")})
        run = PlaygroundRun(job_id=book, task="translate", pages="2-3", variants=variants, results=[])
        s.add(run)
        s.commit()
        run_id = run.id
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "done" and run.progress == 100
        assert s.scalar(select(func.count()).select_from(TranslationCache)) == before  # producción intacta
        a, b = run.results
        assert set(a["segments"]) == {"p002_s001", "p003_s001"}  # solo rango y solo 'translate'
        assert a["segments"]["p002_s001"]["output"] == "ES Text 2 by Carole"  # restaurado desde placeholders
        assert a["calls"] == 1 and a["error"] is None and a["seconds"] >= 0
    assert spies["fake"].seen[0]["text"] == "Text 2 by __NAME_001__"  # protección guardada, sin reproteger
    assert spies["fake"].prompts is None and spies["deepseek"].prompts == {"translate": "BORRADOR"}


def test_failing_variant_does_not_break_others(db, book, monkeypatch):
    from app.db.models import PlaygroundRun

    def factory(rs, prompts=None):
        if rs.provider == "deepseek":
            return Spy(fail=FatalAPIError("DeepSeek respondió 401: llave"))
        return Spy()

    monkeypatch.setattr(rsmod, "make_translator", factory)
    with db() as s:
        run = PlaygroundRun(job_id=book, task="translate", pages="1",
                            variants=pg.validate_variants([{"provider": "deepseek", "model": "m"}, {"provider": "fake"}],
                                                          "translate", {}), results=[])
        s.add(run)
        s.commit()
        run_id = run.id
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        bad, ok = run.results
        assert run.status == "done"
        assert "DeepSeek" in bad["error"] and ok["error"] is None and ok["segments"]["p001_s001"]["output"]


def test_no_balance_pauses_run_and_resume_skips_done_blocks(db, book, monkeypatch):
    """Sin saldo (402) la evaluación se pausa conservando lo hecho; al reanudar solo se traducen los pendientes."""
    from app.db.models import PlaygroundRun

    calls = {"n": 0, "quota": True}

    class Flaky(Spy):
        def translate_batch(self, items, context):
            calls["n"] += 1
            if calls["quota"] and items[0]["id"] != "p001_s001":
                time.sleep(0.2)  # el bloque bueno termina antes que los que fallan (hay concurrencia)
                raise FatalAPIError('DeepSeek respondió 402: {"error": "Insufficient Balance"}')
            return super().translate_batch(items, context)

    spies = []

    def factory(rs, prompts=None):
        spies.append(Flaky())
        return spies[-1]

    monkeypatch.setattr(rsmod, "make_translator", factory)
    monkeypatch.setattr(pg, "BATCH_ITEMS", 1)  # un bloque por llamada para cortar a mitad
    with db() as s:
        run = PlaygroundRun(job_id=book, task="translate", scope="book", pages="1-3",
                            variants=pg.validate_variants([{"provider": "deepseek", "model": "m"}] * 2,
                                                          "translate", {}), results=[])
        s.add(run)
        s.commit()
        run_id = run.id
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "paused" and "saldo" in run.error and run.results == []
        assert len(run.state["caches"]["A"]) == 1  # el bloque ya traducido queda guardado
    calls["quota"] = False
    seen_before = sum(len(x.seen) for x in spies)
    pg.resume(run_id)
    with db() as s:
        assert s.get(PlaygroundRun, run_id).status == "queued"
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "done" and len(run.results) == 2 and run.error is None
        a, b = run.results
        assert all(o["output"] for o in a["segments"].values()) and len(a["segments"]) == 3
    # A tradujo 2 bloques nuevos al reanudar (no repite el ya hecho) y B sus 3
    assert sum(len(x.seen) for x in spies) - seen_before == 2 + 3
    with pytest.raises(ValueError):
        pg.resume(run_id)  # solo se reanuda lo pausado


def test_detect_chapters_without_toc(db):
    from app.db.models import Document, Job, Page, Segment

    with db() as s:
        doc = Document(original_name="sin_indice.pdf", path="/x.pdf", sha256="z", page_count=9)
        job = Job(document=doc, status="done", options={})
        s.add(job)
        s.flush()
        for n in range(1, 10):
            page = Page(job_id=job.id, number=n, width=400, height=600, kind="digital")
            segs = [Segment(seg_key=f"p{n:03d}_s002", bbox=[40, 300, 360, 500], block_type="body",
                            source_text="Body text " * 20, source_html="x", style={"size": 10}, action="translate"),
                    Segment(seg_key=f"p{n:03d}_s001", bbox=[40, 20, 360, 30], block_type="heading",
                            source_text="The Secrets of Astrology", source_html="x", style={"size": 9}, action="translate")]  # cabecera
            if n in (2, 5):
                segs.append(Segment(seg_key=f"p{n:03d}_s003", bbox=[40, 80, 360, 120], block_type="heading",
                                    source_text=f"The Planet {n}", source_html="x", style={"size": 22}, action="translate"))
            if n == 8:
                segs.append(Segment(seg_key="p008_s003", bbox=[40, 90, 360, 110], block_type="body",
                                    source_text="Chapter 3", source_html="x", style={"size": 11}, action="translate"))
            page.segments = segs
            s.add(page)
        s.commit()
        chapters = pg.detect_chapters(s, job)
    assert [(c["title"], c["pages"]) for c in chapters] == [
        ("Inicio", "1-1"), ("The Planet 2", "2-4"), ("The Planet 5", "5-7"), ("Chapter 3", "8-9")]
    assert all(c["source"] == "detected" for c in chapters)


def test_detect_chapters_scanned_ocr(db):
    """Libro escaneado: todos los bloques son «ocr» y la página puede no tener altura guardada."""
    from app.db.models import Document, Job, Page, Segment

    with db() as s:
        doc = Document(original_name="escaneado.pdf", path="/x.pdf", sha256="o", page_count=6)
        job = Job(document=doc, status="done", options={"mode": "prepare"})
        s.add(job)
        s.flush()
        for n in range(1, 7):
            page = Page(job_id=job.id, number=n, width=400, height=0 if n == 4 else 600, kind="scanned")
            segs = [Segment(seg_key=f"p{n:03d}_s002", bbox=[40, 200, 360, 580], block_type="ocr",
                            source_text="Ocr body text " * 20, source_html="x", style={"size": 10}, action="translate")]
            if n == 2:
                segs.append(Segment(seg_key="p002_s001", bbox=[40, 60, 360, 100], block_type="ocr",
                                    source_text="THE SUN", source_html="x", style={"size": 24}, action="translate"))
            if n == 4:
                segs.append(Segment(seg_key="p004_s001", bbox=[40, 60, 360, 80], block_type="ocr",
                                    source_text="CHAPTER 3", source_html="x", style={"size": 11}, action="translate"))
            if n == 5:  # grande pero al pie: no es título
                segs.append(Segment(seg_key="p005_s001", bbox=[40, 520, 360, 560], block_type="ocr",
                                    source_text="Figure caption", source_html="x", style={"size": 24}, action="translate"))
            page.segments = segs
            s.add(page)
        s.commit()
        chapters = pg.detect_chapters(s, job)
    assert [(c["title"], c["pages"]) for c in chapters] == [("Inicio", "1-1"), ("THE SUN", "2-3"), ("CHAPTER 3", "4-6")]


def test_book_pages_endpoint(db, book):
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get(f"/api/admin/playground/books/{book}/pages")
    assert r.status_code == 200, r.text
    assert r.json() == [{"number": n, "kind": "digital", "blocks": 2} for n in (1, 2, 3)]
    assert c.get("/api/admin/playground/books/999999/pages").status_code == 404


def test_correct_task_on_digitized_book(db, monkeypatch):
    from app.db.models import Document, Job, Page, PlaygroundRun, Segment

    with db() as s:
        doc = Document(original_name="scan.pdf", path="/x.pdf", sha256="y", page_count=1)
        job = Job(document=doc, status="done", options={"mode": "digitize", "ocr_lang": "en"})
        s.add(job)
        s.flush()
        page = Page(job_id=job.id, number=1, width=1, height=1, kind="scanned")
        page.segments = [Segment(seg_key="p001_s001", bbox=[0, 0, 1, 1], block_type="body", source_text="Tbe rnoon",
                                 source_html="Tbe rnoon", action="translate"),
                         Segment(seg_key="p001_s002", bbox=[0, 0, 1, 1], block_type="body", source_text="12",
                                 source_html="12", action="translate")]  # sin letras: no se corrige
        s.add(page)
        s.flush()
        assert pg.job_task(job) == "correct"
        run = PlaygroundRun(job_id=job.id, task="correct", pages="1",
                            variants=pg.validate_variants([{"provider": "fake"}], "correct", {}), results=[])
        s.add(run)
        s.commit()
        run_id = run.id
    monkeypatch.setattr(rsmod, "make_translator", lambda rs, prompts=None: Spy())
    pg.execute(run_id)
    with db() as s:
        res = s.get(PlaygroundRun, run_id).results[0]
        assert res["segments"] == {"p001_s001": {"output": "Tbe moon", "issues": []}}


def test_api(db, book, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    assert set(c.get("/api/admin/prompts").json()) == {"translate", "correct", "shorten", "names"}
    d = c.post("/api/admin/prompt-drafts", json={"task": "translate", "name": "Más literal", "text": "P1"}).json()
    assert c.put(f"/api/admin/prompt-drafts/{d['id']}", json={"text": "P2"}).json()["text"] == "P2"
    assert c.post("/api/admin/prompt-drafts", json={"task": "x", "name": "n", "text": "t"}).status_code == 400
    assert any(b["id"] == book and b["task"] == "translate" for b in c.get("/api/admin/playground/books").json())

    body = {"job_id": book, "pages": "1-2", "variants": [{"provider": "fake"}, {"provider": "fake", "prompt": d["id"]}]}
    r = c.post("/api/admin/playground/runs", json=body)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "queued" and run["variants"][1]["prompt_text"] == "P2"
    c.put(f"/api/admin/prompt-drafts/{d['id']}", json={"text": "P3"})  # editar después no cambia la ejecución
    detail = c.get(f"/api/admin/playground/runs/{run['id']}").json()
    assert detail["variants"][1]["prompt_text"] == "P2"
    assert [x["key"] for x in detail["segments"]] == ["p001_s001", "p002_s001"]
    assert detail["segments"][0]["source"] == "Text 1 by Carole"
    assert c.post(f"/api/admin/playground/runs/{run['id']}/cancel").json()["status"] == "cancelled"
    assert any(x["id"] == run["id"] for x in c.get("/api/admin/playground/runs").json())

    assert c.post("/api/admin/playground/runs", json={**body, "pages": "1-9"}).status_code == 400
    # varias páginas sueltas
    r = c.post("/api/admin/playground/runs", json={**body, "scope": "pages", "pages": "3, 1"})
    assert r.status_code == 200, r.text
    assert r.json()["pages"] == "1,3" and r.json()["scope"] == "pages"
    detail = c.get(f"/api/admin/playground/runs/{r.json()['id']}").json()
    assert [x["key"] for x in detail["segments"]] == ["p001_s001", "p003_s001"]
    c.post(f"/api/admin/playground/runs/{r.json()['id']}/cancel")
    # estimación y confirmación del libro entero con una variante que consume saldo de DeepSeek
    paid = {"job_id": book, "scope": "book", "pages": "", "variants": [{"provider": "deepseek"}]}
    est = c.post("/api/admin/playground/estimate", json=paid).json()
    assert est["pages"] == 3 and est["blocks"] == 3 and est["needs_confirm"] is True
    assert est["calls_per_variant"] == 1 and est["chars"] == len("Text 1 by __NAME_001__") * 3
    assert c.post("/api/admin/playground/runs", json=paid).status_code == 400  # falta confirmar
    r = c.post("/api/admin/playground/runs", json={**paid, "confirm": True})
    assert r.status_code == 200 and r.json()["pages"] == "1-3"
    c.post(f"/api/admin/playground/runs/{r.json()['id']}/cancel")
    free = c.post("/api/admin/playground/estimate", json={**paid, "variants": [{"provider": "fake"}]}).json()
    assert free["needs_confirm"] is False
    assert c.post("/api/admin/playground/runs", json={**body, "variants": []}).status_code == 400
    assert c.delete(f"/api/admin/prompt-drafts/{d['id']}").status_code == 200
