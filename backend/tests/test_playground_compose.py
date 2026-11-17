"""Playground, mesa de PDF: cada variante se maqueta en su PDF, la página se sirve como imagen con sus bloques,
se vota la mejor y «Probar en la pág. N» vuelve a evaluar solo esa página."""
import os

import pymupdf
import pytest

from app import playground as pg
from app import runtime_settings as rsmod


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data_playground"))
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
    while (claimed := worker.claim_job()) is not None:
        worker.process(claimed)
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "done"
    return jid


class Marker:
    """Variante falsa: antepone una marca a cada bloque y cuenta lo que se le pide. skip: bloques sin respuesta."""

    def __init__(self, mark, seen, skip=()):
        self.mark, self.seen, self.skip, self.model, self.prompts, self.meter = mark, seen, set(skip), "m", None, None

    def translate_batch(self, items, context):
        self.seen.extend(it["id"] for it in items)
        if self.meter:
            self.meter.add(10, 5, None)
        return {it["id"]: {"id": it["id"], "translation": f"{self.mark} {it['text']}"}
                for it in items if it["id"] not in self.skip}

    def extract_names(self, text):
        return []


def _texts(path) -> list[str]:
    with pymupdf.open(path) as d:
        return [p.get_text() for p in d]


def _run_queue():
    while (rid := pg.claim_run()) is not None:
        pg.execute(rid)


def test_variant_pdf_page_data_votes_and_try(client, job_id, monkeypatch):
    from app.db.models import PlaygroundRun
    from app.db.session import SessionLocal

    seen: list[str] = []
    marks = {"m": "VARIANTE"}
    skipped = "p004_s002"

    def factory(rs, prompts=None):
        return Marker(marks["m"] if not prompts else "BORRADOR", seen, skip=[skipped])

    monkeypatch.setattr(rsmod, "make_translator", factory)
    body = {"job_id": job_id, "scope": "pages", "pages": "4-5",
            "variants": [{"provider": "deepseek", "model": "deepseek-flash"}, {"provider": "fake"}]}
    r = client.post("/api/admin/playground/runs", json=body)
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    _run_queue()

    run = client.get(f"/api/admin/playground/runs/{run_id}").json()
    assert run["status"] == "done", run["error"]
    assert run["production"] is True and run["page_list"] == [4, 5]
    a, b = run["results"]
    assert a["composed"] and b["composed"] and "pdf" not in a  # la ruta no sale de la API
    with SessionLocal() as s:
        res_a = s.get(PlaygroundRun, run_id).results[0]
        prod_pdf = s.get(PlaygroundRun, run_id).job_id
    from app.db.models import Job

    with SessionLocal() as s:
        job = s.get(Job, prod_pdf)
        orig, prod = _texts(job.document.path), _texts(job.output_path)
    var = _texts(res_a["pdf"])
    assert len(var) == len(orig)
    assert "VARIANTE" in var[3] and "VARIANTE" in var[4]  # páginas evaluadas, con la salida de la variante
    assert var[0] == orig[0] and var[2] == orig[2]  # las no evaluadas quedan como el original
    assert "VARIANTE" not in prod[3]  # producción intacta
    # el bloque sin respuesta de la variante se maqueta con la traducción de producción
    assert a["segments"][skipped]["output"] is None
    page = client.get(f"/api/admin/playground/runs/{run_id}/pages/4").json()
    blk = next(x for x in page["blocks"] if x["key"] == skipped)
    assert "sin resultado" in blk["cols"]["A"]["warnings"]
    assert blk["cols"]["prod"]["output"] and blk["bbox"] and page["width"] and page["height"]
    assert set(page["metrics"]) == {"prod", "A", "B"}
    assert page["metrics"]["A"]["warn_blocks"] >= 1 and page["metrics"]["A"]["stale"] is False
    assert any(x["cols"]["A"]["fit"] is not None for x in page["blocks"])  # escala de la maquetación
    assert run["summary"]["A"]["warn_pages"] == [4]

    for col in ("orig", "prod", "A", "B"):
        img = client.get(f"/api/admin/playground/runs/{run_id}/pages/4/image?col={col}&dpi=40")
        assert img.status_code == 200 and img.content[:4] == b"\x89PNG", col
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/4/image?col=D").status_code == 404
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/2").status_code == 404  # fuera de la evaluación

    # votos
    assert client.put(f"/api/admin/playground/runs/{run_id}/votes/4", json={"vote": "A"}).json()["votes"] == {"4": "A"}
    assert client.put(f"/api/admin/playground/runs/{run_id}/votes/5", json={"vote": "tie"}).status_code == 200
    assert client.put(f"/api/admin/playground/runs/{run_id}/votes/5", json={"vote": "Z"}).status_code == 400
    client.put(f"/api/admin/playground/runs/{run_id}/votes/5", json={"vote": None})
    run = client.get(f"/api/admin/playground/runs/{run_id}").json()
    assert run["votes"] == {"4": "A"} and run["summary"]["A"]["won"] == 1
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/4").json()["vote"] == "A"

    # probar la página 5 con un borrador: solo se traducen sus bloques y solo cambia esa página
    d = client.post("/api/admin/prompt-drafts", json={"task": "translate", "name": "Otro", "text": "P"}).json()
    before = _texts(res_a["pdf"])
    seen.clear()
    r = client.post(f"/api/admin/playground/runs/{run_id}/variants/A/try",
                    json={"page": 5, "variant": {"provider": "deepseek", "model": "deepseek-flash", "prompt": d["id"]}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued" and r.json()["trying"] == {"label": "A", "page": 5}
    assert client.post(f"/api/admin/playground/runs/{run_id}/variants/A/try",
                       json={"page": 5, "variant": {"provider": "fake"}}).status_code == 409  # en curso
    _run_queue()
    run = client.get(f"/api/admin/playground/runs/{run_id}").json()
    assert run["status"] == "done" and run["error"] is None and run["trying"] is None
    assert seen and all(k.startswith("p005_") for k in seen)
    a = run["results"][0]
    assert a["stale_pages"] == [4] and run["variants"][0]["prompt_name"] == "Otro"
    assert a["calls"] > 1  # el uso de la prueba se suma al de la variante
    after = _texts(res_a["pdf"])
    assert after[3] == before[3] and "BORRADOR" in after[4] and "BORRADOR" not in before[4]
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/4").json()["metrics"]["A"]["stale"] is True
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/5").json()["metrics"]["A"]["stale"] is False
    # misma configuración en la página 4: deja de estar desactualizada
    client.post(f"/api/admin/playground/runs/{run_id}/variants/A/try",
                json={"page": 4, "variant": {"provider": "deepseek", "model": "deepseek-flash", "prompt": d["id"]}})
    _run_queue()
    assert client.get(f"/api/admin/playground/runs/{run_id}").json()["results"][0]["stale_pages"] == []
    assert client.post(f"/api/admin/playground/runs/{run_id}/variants/A/try",
                       json={"page": 2, "variant": {"provider": "fake"}}).status_code == 400


def test_old_run_without_pdf_is_composed_without_translating(client, job_id, monkeypatch):
    from app.db.models import PlaygroundRun
    from app.db.session import SessionLocal

    calls = []
    monkeypatch.setattr(rsmod, "make_translator", lambda rs, prompts=None: Marker("X", calls))
    with SessionLocal() as s:
        run = PlaygroundRun(job_id=job_id, task="translate", scope="page", pages="4",
                            variants=pg.validate_variants([{"provider": "deepseek", "model": "deepseek-flash"}], "translate", {}),
                            results=[{"label": "A", "segments": {"p004_s001": {"output": "ANTIGUA", "issues": []}},
                                      "seconds": 1, "calls": 1, "error": None}], status="done")
        s.add(run)
        s.commit()
        run_id = run.id
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/4/image?col=A").status_code == 409
    assert client.post(f"/api/admin/playground/runs/{run_id}/compose").json()["status"] == "queued"
    _run_queue()
    run = client.get(f"/api/admin/playground/runs/{run_id}").json()
    assert run["status"] == "done" and run["results"][0]["composed"] and calls == []
    assert client.get(f"/api/admin/playground/runs/{run_id}/pages/4/image?col=A").status_code == 200


def test_block_warnings():
    assert pg.block_warnings({"output": "x", "issues": [], "fit": 0.95}) == []
    assert pg.block_warnings({"output": "x", "issues": ["a"], "fit": 0.7}) == ["a", "escala 0,70: el texto no cabe en su caja"]
    assert pg.block_warnings({"output": None}) == ["sin resultado"]
    assert pg.block_warnings(None) == []


def test_prepare_mode_extracts_without_translating(client, sample_pdf, monkeypatch):
    """Subir un libro «para el Playground» solo lo analiza y protege: ni traduce, ni maqueta, ni llama a modelos."""
    from app import worker
    from app.db.models import Job, Page, Segment
    from app.db.session import SessionLocal

    calls = []
    no_key = {"on": True}

    def factory(rs, prompts=None):
        if no_key["on"]:  # preparar no necesita llave: no debe ni crear el traductor
            raise RuntimeError("Falta DEEPSEEK_API_KEY")
        return Marker("VARIANTE", calls)

    monkeypatch.setattr(rsmod, "make_translator", factory)
    r = client.post("/api/jobs", files={"file": ("prep.pdf", sample_pdf.read_bytes(), "application/pdf")},
                    data={"rights_confirmed": "true", "mode": "prepare"})
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    assert r.json()["mode"] == "prepare" and [st["key"] for st in r.json()["stages"]][-1] == "done"
    while (claimed := worker.claim_job()) is not None:
        worker.process(claimed)
    st = client.get(f"/api/jobs/{jid}").json()
    assert st["status"] == "done" and st["output_name"] is None
    assert calls == []  # ninguna llamada al modelo
    with SessionLocal() as s:
        segs = s.query(Segment).join(Page).filter(Page.job_id == jid, Segment.action == "translate").all()
        assert segs and all(sg.translation is None and sg.protected_text for sg in segs)
        assert s.get(Job, jid).output_path is None
    book = next(b for b in client.get("/api/admin/playground/books").json() if b["id"] == jid)
    assert book["prepared"] and not book["production"] and book["blocks"] == len(segs)
    assert client.get(f"/api/admin/playground/books/{jid}/chapters").status_code == 200

    # ya preparado, la evaluación funciona igual (sin columna de producción)
    no_key["on"] = False
    run = client.post("/api/admin/playground/runs", json={"job_id": jid, "scope": "page", "pages": "4",
                                                          "variants": [{"provider": "deepseek", "model": "deepseek-flash"}]}).json()
    _run_queue()
    detail = client.get(f"/api/admin/playground/runs/{run['id']}").json()
    assert detail["status"] == "done" and detail["production"] is False and detail["results"][0]["composed"]
    assert calls and all(k.startswith("p004_") for k in calls)
    page = client.get(f"/api/admin/playground/runs/{run['id']}/pages/4").json()
    assert set(page["metrics"]) == {"A"}
    assert client.get(f"/api/admin/playground/runs/{run['id']}/pages/4/image?col=prod").status_code == 409


def test_history_keeps_every_attempt_grouped_by_book(client, job_id, monkeypatch):
    """Cada variante evaluada y cada «Probar en la pág.» queda en el historial con su configuración, su uso y su
    salida; una prueba posterior no pisa la salida (ni la copia del PDF) de la anterior."""
    marks = {"m": "PRIMERA"}
    monkeypatch.setattr(rsmod, "make_translator", lambda rs, prompts=None: Marker(marks["m"], []))
    r = client.post("/api/admin/playground/runs", json={
        "job_id": job_id, "scope": "page", "pages": "4",
        "variants": [{"provider": "deepseek", "model": "deepseek-flash", "thinking": "disabled"}]})
    run_id = r.json()["id"]
    _run_queue()
    marks["m"] = "SEGUNDA"
    r = client.post(f"/api/admin/playground/runs/{run_id}/variants/A/try",
                    json={"page": 4, "variant": {"provider": "deepseek", "model": "deepseek-v4-pro", "thinking": "high"}})
    assert r.status_code == 200, r.text
    _run_queue()

    books = client.get("/api/admin/playground/history").json()
    book = next(b for b in books if b["job_id"] == job_id)
    assert book["book"] and book["attempts"] >= 2 and book["tokens_in"] > 0

    hist = client.get(f"/api/admin/playground/history/{job_id}").json()
    mine = [a for a in hist["attempts"] if a["run_id"] == run_id]
    assert [a["kind"] for a in mine] == ["try", "run"]  # la más nueva primero
    tried, first = mine
    assert first["config"]["model"] == "deepseek-flash" and tried["config"]["model"] == "deepseek-v4-pro"
    assert tried["pages"] == "4" and "prompt_text" not in tried["config"]
    assert first["snapshot"] and tried["snapshot"]
    # la prueba guarda solo su propio uso (no el acumulado de la variante)
    assert tried["calls"] >= 1 and tried["tokens_in"] == 10 * tried["calls"]

    d1 = client.get(f"/api/admin/playground/attempts/{first['id']}").json()
    d2 = client.get(f"/api/admin/playground/attempts/{tried['id']}").json()
    assert d1["blocks"] and all(b["output"].startswith("PRIMERA") for b in d1["blocks"] if b["output"])
    assert all(b["output"].startswith("SEGUNDA") for b in d2["blocks"] if b["output"])
    assert "prompt_text" in d2["config"] and d2["page_list"] == [4]

    # la copia del primer intento conserva su salida aunque la prueba rehízo la página en el PDF de la variante
    from app.db.models import PlaygroundAttempt
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        assert "PRIMERA" in _texts(s.get(PlaygroundAttempt, first["id"]).pdf)[0]
        assert "SEGUNDA" in _texts(s.get(PlaygroundAttempt, tried["id"]).pdf)[0]
    img = client.get(f"/api/admin/playground/attempts/{first['id']}/pages/4/image?dpi=40")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert client.get(f"/api/admin/playground/attempts/{first['id']}/pages/5/image").status_code == 404
    assert client.get("/api/admin/playground/attempts/999999").status_code == 404
