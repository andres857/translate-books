"""Matriz de autorización: visitante, user y admin sobre las rutas existentes, y propiedad de los trabajos."""
import os

import pytest

from .conftest import auth_client


@pytest.fixture(scope="module")
def ctx(tmp_path_factory, sample_pdf):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from fastapi.testclient import TestClient

    from app.main import app

    owner, other, admin = auth_client(app, "user"), auth_client(app, "user"), auth_client(app, "admin")
    r = owner.post("/api/jobs", files={"file": ("mio.pdf", sample_pdf.read_bytes(), "application/pdf")},
                   data={"rights_confirmed": "true"})
    assert r.status_code == 200, r.text
    return {"app": app, "anon": TestClient(app), "owner": owner, "other": other, "admin": admin,
            "job": r.json()["id"]}


def test_visitor_gets_401_everywhere(ctx):
    anon, job = ctx["anon"], ctx["job"]
    for path in ("/api/jobs", f"/api/jobs/{job}", f"/api/jobs/{job}/events", "/api/settings", "/api/users",
                 f"/api/admin/jobs/{job}/summary", "/api/admin/playground/books", "/api/glossary",
                 f"/api/jobs/{job}/pages/1/preview", f"/api/jobs/{job}/download"):
        assert anon.get(path).status_code == 401, path
    assert anon.get("/api/health").json() == {"ok": True}


def test_owner_sees_and_manages_own_job(ctx):
    owner, job = ctx["owner"], ctx["job"]
    assert [j["id"] for j in owner.get("/api/jobs").json()] == [job]
    assert owner.get(f"/api/jobs/{job}").status_code == 200
    assert owner.get(f"/api/jobs/{job}/pages").status_code == 200
    assert owner.get(f"/api/jobs/{job}/pages/1/preview", params={"version": "original"}).status_code == 200
    assert owner.post(f"/api/jobs/{job}/cancel").json()["status"] == "cancelled"
    assert owner.post(f"/api/jobs/{job}/resume").json()["status"] == "queued"
    assert owner.post(f"/api/jobs/{job}/cancel").status_code == 200
    assert "max_upload_mb" in owner.get("/api/health").json()
    assert owner.get("/api/settings").status_code == 200


def test_other_user_cannot_reach_the_job(ctx):
    other, job = ctx["other"], ctx["job"]
    assert other.get("/api/jobs").json() == []
    for path in (f"/api/jobs/{job}", f"/api/jobs/{job}/events", f"/api/jobs/{job}/pages",
                 f"/api/jobs/{job}/pages/1/preview?version=original", f"/api/jobs/{job}/download",
                 f"/api/jobs/{job}/report"):
        assert other.get(path).status_code == 404, path
    for action in ("cancel", "resume"):
        assert other.post(f"/api/jobs/{job}/{action}").status_code == 404


def test_user_is_denied_admin_operations(ctx):
    owner, job = ctx["owner"], ctx["job"]
    assert owner.delete(f"/api/jobs/{job}").status_code == 403
    assert owner.put("/api/settings", json={"provider": "fake"}).status_code == 403
    assert owner.post("/api/settings/test").status_code == 403
    for path in (f"/api/admin/jobs/{job}/summary", f"/api/admin/jobs/{job}/chapters", "/api/admin/prompts",
                 "/api/admin/playground/books", "/api/glossary", "/api/protected-terms", "/api/files/1",
                 "/api/users"):
        assert owner.get(path).status_code == 403, path
    assert owner.post("/api/glossary", json={"source": "a", "target": "b"}).status_code == 403
    assert owner.post("/api/jobs/presign", json={"filename": "x.pdf", "size": 10}).status_code != 403  # puede subir


def test_user_cannot_prepare_for_playground(ctx, sample_pdf):
    r = ctx["owner"].post("/api/jobs", files={"file": ("p.pdf", sample_pdf.read_bytes(), "application/pdf")},
                          data={"rights_confirmed": "true", "mode": "prepare"})
    assert r.status_code == 403


def test_admin_sees_every_job(ctx):
    admin, job = ctx["admin"], ctx["job"]
    assert job in [j["id"] for j in admin.get("/api/jobs").json()]
    assert admin.get(f"/api/admin/jobs/{job}/summary").status_code == 200


def test_events_stream_stops_when_session_is_revoked(ctx):
    """El SSE revalida la sesión en cada vuelta: al revocarla, el flujo termina con `unauthorized`."""
    from app.auth import sessions
    from app.db.models import AuthSession
    from app.db.session import session_scope

    from app.db.models import Job

    owner, job = ctx["owner"], ctx["job"]  # última prueba del módulo: revoca las sesiones del dueño
    with session_scope() as db:
        db.get(Job, job).status = "running"  # sin estado final: el flujo seguiría abierto
    with owner.stream("GET", f"/api/jobs/{job}/events") as r:
        assert r.status_code == 200
        lines = r.iter_lines()
        assert next(lines).startswith("data: ")
        with session_scope() as db:
            sessions.revoke_all(db, owner.user.id)
        rest = "\n".join(lines)
    assert "event: unauthorized" in rest
    with session_scope() as db:
        assert db.query(AuthSession).filter(AuthSession.user_id == owner.user.id,
                                            AuthSession.revoked_at.is_(None)).count() == 0
