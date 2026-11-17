"""#14: el JSON de las rutas con `response_model` es byte a byte el de antes del cambio.

Los snapshots de `tests/snapshots/` se generaron con el código anterior a los esquemas. Los valores que cambian
en cada ejecución (ids, correos, token CSRF, totales) se sustituyen por marcadores antes de comparar; el resto
(orden de las claves, `null`, números, acentos) se compara tal cual. `UPDATE_SNAPSHOTS=1` los regenera.
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import runtime_settings as rsmod

SNAPSHOTS = Path(__file__).parent / "snapshots"
KEY = "sk-test-0123456789abcd"
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
UPDATED = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
TEMP_EXP = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
SESSION_EXP = datetime(2099, 1, 1, tzinfo=timezone.utc)
REAUTH_AT = datetime(2099, 1, 1, 0, 0, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ["FAKE_TRANSLATOR"] = "true"
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.cli import migrate

    migrate()
    from app.main import app

    return app


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(rsmod, "settings_path", lambda: tmp_path / "settings.json")
    rsmod.update({"provider": "deepseek", "deepseek_api_key": KEY, "deepseek_model": "deepseek-v4-pro",
                  "deepseek_thinking": "low", "deepseek_concurrency": 4})


def check(name: str, body: bytes, replace: list[tuple[str, str]]) -> None:
    text = body.decode()
    for old, new in replace:
        assert old in text, (old, text)
        text = text.replace(old, new)
    path = SNAPSHOTS / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert text == path.read_text(encoding="utf-8")


def _client(app, role: str, *, temp_exp: datetime | None = None, reauth: bool = False):
    """Cliente con cuenta y sesión de fechas fijas (correo único: la BD de pruebas se conserva)."""
    from app.db.models import AuthSession, User
    from app.db.session import session_scope

    from .conftest import auth_client, make_user

    user = make_user(role, email=f"snap-{role}-{uuid.uuid4().hex[:10]}@example.com")
    with session_scope() as db:
        u = db.get(User, user.id)
        u.name = "Ñandú Pérez"
        u.created_at, u.updated_at, u.temp_password_expires_at = CREATED, UPDATED, temp_exp
    c = auth_client(app, user=user)
    with session_scope() as db:
        s = db.query(AuthSession).filter(AuthSession.user_id == user.id).one()
        s.expires_at, s.reauth_at = SESSION_EXP, REAUTH_AT if reauth else None
    return c


def _jobs(owner_id: int) -> list[tuple[int, int]]:
    """Tres trabajos que cubren los tres modos, `null` y no `null`. Devuelve [(job_id, document_id)]."""
    from app.db.models import Document, Job, Page
    from app.db.session import session_scope

    specs = [
        (dict(original_name="libro-traducir.pdf", page_count=4, title_es="Astrología básica"),
         dict(status="running", stage="translate", progress=40.0, current_page=3, options={}),
         {3: ["ocr"], 1: [], 4: ["longitud", "glosario"]}),
        (dict(original_name="escaneo.pdf", page_count=2, title_es=None),
         dict(status="done", stage="done", progress=100.0, current_page=2, output_path="/nope/out/escaneo-ocr.pdf",
              options={"mode": "digitize", "ocr_lang": "es", "correct": True, "recompose": True,
                       "recompose_error": "Falló la recomposición"}),
         {}),
        (dict(original_name="preparar.pdf", page_count=1, title_es="Preparado"),
         dict(status="failed", stage="glossary", progress=12.5, current_page=None, error="Algo falló «aquí»",
              options={"mode": "prepare"}),
         {1: ["glosario"]}),
    ]
    out = []
    with session_scope() as db:
        for doc, job, reviews in specs:
            d = Document(path="/nope/x.pdf", sha256="0" * 64, **doc)
            j = Job(document=d, owner_id=owner_id, **job)
            db.add(j)
            for number in range(1, d.page_count + 1):
                db.add(Page(job=j, number=number, width=420, height=595, kind="digital",
                            needs_review=number in reviews, review_reasons=reviews.get(number, [])))
            db.flush()
            out.append((j.id, d.id))
    return out


def _job_ids(ids: list[tuple[int, int]]) -> list[tuple[str, str]]:
    rep = []
    for n, (job_id, doc_id) in enumerate(ids, 1):
        rep += [(f'"id":{job_id},', f'"id":"<job{n}>",'), (f'"document_id":{doc_id},', f'"document_id":"<doc{n}>",')]
    return rep


def _user_ids(c) -> list[tuple[str, str]]:
    return [(f'"id":{c.user.id},', '"id":"<user>",'), (c.user.email, "<email>")]


def test_jobs_snapshot(app):
    c = _client(app, "user")
    ids = _jobs(c.user.id)
    for n, (job_id, _) in enumerate(ids, 1):
        r = c.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200, r.text
        check(f"job_{n}", r.content, _job_ids(ids)[2 * n - 2:2 * n])
    r = c.get("/api/jobs")
    assert r.status_code == 200, r.text
    check("jobs", r.content, _job_ids(ids))


def test_auth_me_snapshot(app):
    from app.auth import sessions

    for name, c in (("me_user", _client(app, "user")),
                    ("me_admin", _client(app, "admin", temp_exp=TEMP_EXP, reauth=True))):
        r = c.get("/api/auth/me")
        assert r.status_code == 200, r.text
        token = c.cookies.get(sessions.cookie_name())
        check(name, r.content, [*_user_ids(c), (sessions.csrf_for(token), "<csrf>")])


def test_settings_snapshot(app, store):
    r = _client(app, "admin").get("/api/settings")
    assert r.status_code == 200, r.text
    check("settings_admin", r.content, [])
    r = _client(app, "user").get("/api/settings")
    assert r.status_code == 200, r.text
    check("settings_user", r.content, [])


def test_users_snapshot(app):
    """Una página de `GET /api/users` con una sola cuenta (la de la prueba): el total depende de la BD."""
    from sqlalchemy import func, select

    from app.db.models import User
    from app.db.session import session_scope

    admin = _client(app, "admin", temp_exp=TEMP_EXP)
    with session_scope() as db:
        total = db.scalar(select(func.count()).select_from(User))
        position = db.scalar(select(func.count()).select_from(User).where(User.id <= admin.user.id))
    r = admin.get(f"/api/users?page={position}&page_size=1")
    assert r.status_code == 200, r.text
    check("users", r.content, [*_user_ids(admin), (f'"total":{total},', '"total":"<total>",'),
                               (f'"page":{position},', '"page":"<page>",')])


# rutas de estos routers que devuelven archivos o PNG: no llevan `response_model`
NOT_JSON = {("GET", "/api/jobs/{job_id}/download"), ("GET", "/api/jobs/{job_id}/report"),
            ("GET", "/api/jobs/{job_id}/pages/{number}/preview")}


def test_json_routes_declare_response_model():
    """Recorre los routers (la app los incluye de forma perezosa: `app.routes` no lista sus rutas)."""
    from fastapi.routing import APIRoute

    from app.api import routes_auth, routes_jobs, routes_settings, routes_users

    checked, missing = 0, []
    for router in (routes_jobs.router, routes_settings.router, routes_auth.router, routes_users.router):
        routes = [r for r in router.routes if isinstance(r, APIRoute)]
        assert routes, router.prefix
        for route, method in ((r, m) for r in routes for m in r.methods):
            if (method, route.path) in NOT_JSON:
                assert route.response_model is None, route.path
                continue
            checked += 1
            if route.response_model is None:
                missing.append((method, route.path))
    assert not missing
    assert checked >= 20


def test_openapi_describes_job_read(app):
    spec = app.openapi()
    schema = spec["paths"]["/api/jobs/{job_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/JobRead"}
    props = spec["components"]["schemas"]["JobRead"]["properties"]
    assert {"id", "mode", "status", "progress", "stages", "review_pages", "error"} <= set(props)
