"""Playground: variantes (método, modelo, prompt) sobre un capítulo ya procesado, sin tocar producción."""
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
    assert pg.parse_pages("2-3", 10) == (2, 3)
    assert pg.parse_pages(" 5 ", 10) == (5, 5)
    for bad in ("0-2", "3-2", "9-12", "a", "1-50"):
        with pytest.raises(ValueError):
            pg.parse_pages(bad, 60 if bad == "1-50" else 10)


def test_validate_variants():
    v = pg.validate_variants([{"provider": "claude", "model": "opus", "effort": "high"}], "translate", {})
    assert v[0]["label"] == "A" and v[0]["prompt"] == "production" and v[0]["prompt_text"] is None
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "fake"}] * 5, "translate", {})
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "gpt"}], "translate", {})
    with pytest.raises(ValueError):
        pg.validate_variants([{"provider": "claude", "model": "haiku"}], "translate", {})
    with pytest.raises(ValueError):  # borrador de otra tarea
        pg.validate_variants([{"provider": "fake", "prompt": 7}], "translate", {7: ("correct", "x")})
    v = pg.validate_variants([{"provider": "fake", "prompt": 7}], "translate", {7: ("translate", "MI PROMPT")})
    assert v[0]["prompt_text"] == "MI PROMPT"  # se copia al lanzar


def test_run_uses_stored_protection_and_isolated_cache(db, book, monkeypatch):
    from app.db.models import PlaygroundRun, TranslationCache

    spies = {}

    def factory(rs, prompts=None, effort=None):
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

    def factory(rs, prompts=None, effort=None):
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


def test_quota_stops_run(db, book, monkeypatch):
    from app.db.models import PlaygroundRun

    monkeypatch.setattr(rsmod, "make_translator",
                        lambda rs, prompts=None, effort=None: Spy(fail=FatalAPIError("CLAUDE_QUOTA: hit your limit")))
    with db() as s:
        run = PlaygroundRun(job_id=book, task="translate", pages="1",
                            variants=pg.validate_variants([{"provider": "claude", "model": "sonnet"}] * 2,
                                                          "translate", {}), results=[])
        s.add(run)
        s.commit()
        run_id = run.id
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "failed" and "suscripción" in run.error and len(run.results) == 1


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
    monkeypatch.setattr(rsmod, "make_translator", lambda rs, prompts=None, effort=None: Spy())
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
    assert c.post("/api/admin/playground/runs", json={**body, "variants": []}).status_code == 400
    assert c.delete(f"/api/admin/prompt-drafts/{d['id']}").status_code == 200
