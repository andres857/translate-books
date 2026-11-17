"""El worker no pisa una cancelación: si la API cancela entre la última consulta de should_stop y el cierre,
el trabajo (o la evaluación del Playground) sigue 'cancelled' (traductor falso, sin llamadas reales)."""
from types import SimpleNamespace

import pytest

from app import playground as pg
from app import runtime_settings as rsmod
from app import worker


@pytest.fixture(scope="module")
def db():
    from app.cli import migrate

    migrate()
    from app.db.session import SessionLocal

    return SessionLocal


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setattr(rsmod, "load", lambda: rsmod.RuntimeSettings(provider="fake"))


def _set_status(db, model, row_id: int, status: str) -> None:
    """Otra sesión, como la API al pulsar «Detener»."""
    with db() as s:
        s.get(model, row_id).status = status
        s.commit()


@pytest.fixture
def running_job(db, tmp_path):
    from app.db.models import Document, Job

    pdf = tmp_path / "libro.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with db() as s:
        job = Job(document=Document(original_name="libro.pdf", path=str(pdf), sha256="cancel", page_count=1),
                  status="running", options={})
        s.add(job)
        s.commit()
        return job.id


def _fake_pipeline(tmp_path, before_return=None, fail: Exception | None = None):
    def run(*args, **kwargs):
        if before_return:
            before_return()
        if fail:
            raise fail
        return SimpleNamespace(pages=[], title="T", title_es="T", output_pdf=tmp_path / "out.pdf",
                               report_path=tmp_path / "report.json", domain="", glossary_auto=[])
    return run


def test_cancel_before_close_keeps_cancelled(db, running_job, tmp_path, monkeypatch):
    from app.db.models import Job

    monkeypatch.setattr(worker, "run_pipeline",
                        _fake_pipeline(tmp_path, lambda: _set_status(db, Job, running_job, "cancelled")))
    worker.process(running_job)
    with db() as s:
        job = s.get(Job, running_job)
        assert job.status == "cancelled" and job.output_path is None and job.progress != 100.0


def test_without_cancel_job_ends_done(db, running_job, tmp_path, monkeypatch):
    from app.db.models import Job

    monkeypatch.setattr(worker, "run_pipeline", _fake_pipeline(tmp_path))
    worker.process(running_job)
    with db() as s:
        job = s.get(Job, running_job)
        assert job.status == "done" and job.progress == 100.0 and job.output_path == str(tmp_path / "out.pdf")


def test_cancel_then_failure_does_not_become_failed(db, running_job, tmp_path, monkeypatch):
    from app.db.models import Job

    monkeypatch.setattr(worker, "run_pipeline", _fake_pipeline(
        tmp_path, lambda: _set_status(db, Job, running_job, "cancelled"), fail=RuntimeError("se rompió")))
    worker.process(running_job)
    with db() as s:
        job = s.get(Job, running_job)
        assert job.status == "cancelled" and job.error is None


def test_failure_without_cancel_becomes_failed(db, running_job, tmp_path, monkeypatch):
    from app.db.models import Job

    monkeypatch.setattr(worker, "run_pipeline", _fake_pipeline(tmp_path, fail=RuntimeError("se rompió")))
    worker.process(running_job)
    with db() as s:
        job = s.get(Job, running_job)
        assert job.status == "failed" and job.error


def test_cancel_during_recompose_keeps_cancelled(db, running_job, tmp_path, monkeypatch):
    from app.db.models import Job

    out = tmp_path / "out.pdf"
    out.write_bytes(b"%PDF-1.4")
    with db() as s:
        job = s.get(Job, running_job)
        job.output_path, job.options = str(out), {"recompose": [1]}
        s.commit()

    def recompose(*args, **kwargs):
        _set_status(db, Job, running_job, "cancelled")
        raise RuntimeError("no se pudo")

    monkeypatch.setattr(worker, "recompose_page", recompose)
    worker.process(running_job)
    with db() as s:
        job = s.get(Job, running_job)
        assert job.status == "cancelled" and job.options == {"recompose": [1]}


# ---- Playground

@pytest.fixture
def run_id(db):
    from app.db.models import Document, Job, Page, PlaygroundRun, Segment

    with db() as s:
        job = Job(document=Document(original_name="pg.pdf", path="/no/existe.pdf", sha256="pg-cancel", page_count=1),
                  status="done", options={})
        s.add(job)
        s.flush()
        page = Page(job_id=job.id, number=1, width=400, height=600, kind="digital")
        page.segments = [Segment(seg_key="p001_s001", bbox=[0, 0, 10, 10], block_type="body", source_text="Text",
                                 source_html="Text", protected_text="Text", placeholders={}, action="translate")]
        s.add(page)
        run = PlaygroundRun(job_id=job.id, task="translate", pages="1", status="running",
                            variants=pg.validate_variants([{"provider": "fake"}], "translate", {}), results=[])
        s.add(run)
        s.commit()
        return run.id


def _cancel_in_variant(db, run_id, monkeypatch, **override):
    from app.db.models import PlaygroundRun

    real = pg.run_variant

    def run_variant(*args, **kwargs):
        res = real(*args, **kwargs)
        _set_status(db, PlaygroundRun, run_id, "cancelled")
        return {**res, **override}

    monkeypatch.setattr(pg, "run_variant", run_variant)


def test_playground_cancel_during_execute_keeps_cancelled(db, run_id, monkeypatch):
    from app.db.models import PlaygroundRun

    _cancel_in_variant(db, run_id, monkeypatch)
    pg.execute(run_id)
    with db() as s:
        assert s.get(PlaygroundRun, run_id).status == "cancelled"


def test_playground_cancel_is_not_turned_into_paused(db, run_id, monkeypatch):
    from app.db.models import PlaygroundRun

    _cancel_in_variant(db, run_id, monkeypatch, fatal="balance", error="Sin saldo.")
    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "cancelled" and run.error is None


def test_playground_cancelled_before_start_is_not_run(db, run_id, monkeypatch):
    """Cancelada entre claim_run y execute: no se vuelve a poner en 'running' ni se evalúa."""
    from app.db.models import PlaygroundRun

    _set_status(db, PlaygroundRun, run_id, "cancelled")
    monkeypatch.setattr(pg, "run_variant", lambda *a, **k: pytest.fail("no debía evaluarse"))
    pg.execute(run_id)
    with db() as s:
        assert s.get(PlaygroundRun, run_id).status == "cancelled"


def test_playground_without_cancel_ends_done(db, run_id):
    from app.db.models import PlaygroundRun

    pg.execute(run_id)
    with db() as s:
        run = s.get(PlaygroundRun, run_id)
        assert run.status == "done" and run.progress == 100.0 and len(run.results) == 1
