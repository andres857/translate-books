"""Login, sesiones, contraseñas temporales, gestión de cuentas y protecciones de escritura."""
import logging
import os
from datetime import timedelta

import pytest

from .conftest import TEST_PASSWORD, auth_client, login_headers, make_user, session_for


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


@pytest.fixture(autouse=True)
def _fresh_limits(app):
    """La BD de pruebas se conserva entre ejecuciones: cada prueba empieza sin contadores de intentos."""
    from app.db.models import AuthRateLimit
    from app.db.session import session_scope

    with session_scope() as db:
        db.query(AuthRateLimit).delete()


def anon(app):
    from fastapi.testclient import TestClient

    from app.config import get_settings

    c = TestClient(app)
    c.headers.update({"Origin": get_settings().allowed_origins[0], "X-Requested-With": "traductor"})
    return c


def do_login(app, email, password=TEST_PASSWORD):
    c = anon(app)
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code == 200:
        c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return c, r


def test_bootstrap_is_idempotent(app, monkeypatch):
    from app.auth.users import ensure_bootstrap_admin
    from app.config import get_settings
    from app.db.models import User
    from app.db.session import session_scope

    email = "boot-admin@example.com"
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAIL", email)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "arranque-seguro-123")
    get_settings.cache_clear()
    try:
        with session_scope() as db:
            db.query(User).filter(User.email == email).delete()
        for _ in range(2):
            with session_scope() as db:
                ensure_bootstrap_admin(db)
        with session_scope() as db:
            rows = db.query(User).filter(User.email == email).all()
            assert len(rows) == 1 and rows[0].role == "admin" and rows[0].must_change_password
            rows[0].name = "Cambiado a mano"
        # un segundo arranque no toca la cuenta existente
        with session_scope() as db:
            ensure_bootstrap_admin(db)
            assert db.query(User).filter(User.email == email).one().name == "Cambiado a mano"
    finally:
        get_settings.cache_clear()


def test_login_cookie_and_me(app, caplog):
    u = make_user("user")
    caplog.set_level(logging.DEBUG)
    c, r = do_login(app, u.email.upper())  # el correo no distingue mayúsculas
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == u.email and "password_hash" not in body["user"]
    cookie = r.headers["set-cookie"]
    assert "httponly" in cookie.lower() and "samesite=strict" in cookie.lower() and "path=/" in cookie.lower()
    token = c.cookies.get("tl_session") or c.cookies.get("__Host-tl_session")
    assert token and token not in r.text
    assert token not in caplog.text and TEST_PASSWORD not in caplog.text
    me = c.get("/api/auth/me").json()
    assert me["csrf_token"] == body["csrf_token"] and me["session"]["kind"] == "normal"


def test_login_failures_are_generic(app):
    u = make_user("user")
    inactive = make_user("user", active=False)
    _, wrong = do_login(app, u.email, "otra-contraseña-mala")
    _, missing = do_login(app, "nadie-aqui@example.com")
    _, off = do_login(app, inactive.email)
    for r in (wrong, missing, off):
        assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["message"] == missing.json()["message"] == off.json()["message"]


def test_login_rate_limit(app):
    for i in range(10):
        _, r = do_login(app, "ficticio@example.com", f"mala-{i}")
        assert r.status_code == 401
    _, r = do_login(app, "ficticio@example.com", "mala-final")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["code"] == "TOO_MANY_ATTEMPTS"


def test_login_requires_origin_and_app_header(app):
    from fastapi.testclient import TestClient

    u = make_user("user")
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": u.email, "password": TEST_PASSWORD}).status_code == 403
    c.headers.update({"Origin": "https://malo.example", "X-Requested-With": "traductor"})
    assert c.post("/api/auth/login", json={"email": u.email, "password": TEST_PASSWORD}).status_code == 403


def test_temporary_password_flow(app):
    admin = auth_client(app, "admin", reauth=True)
    email = f"nuevo-{os.urandom(4).hex()}@example.com"
    r = admin.post("/api/users", json={"email": email, "name": "Nuevo"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "user"
    temp = r.json()["temporary_password"]
    # el listado nunca la vuelve a mostrar
    assert temp not in admin.get("/api/users?page_size=200").text

    c, r = do_login(app, email, temp)
    assert r.status_code == 200 and r.json()["session"]["kind"] == "restricted"
    # la sesión restringida solo sirve para cambiar la contraseña
    assert c.get("/api/jobs").status_code == 403
    assert c.get("/api/jobs").json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    weak = c.post("/api/auth/change-password", json={"current_password": temp, "new_password": "corta"})
    assert weak.status_code == 400 and weak.json()["code"] == "WEAK_PASSWORD"
    old_cookie = dict(c.cookies)
    r = c.post("/api/auth/change-password", json={"current_password": temp, "new_password": "una-clave-nueva-larga"})
    assert r.status_code == 200 and r.json()["session"]["kind"] == "normal"
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert c.get("/api/jobs").status_code == 200
    # la sesión anterior quedó revocada y la temporal ya no sirve
    from fastapi.testclient import TestClient

    stale = TestClient(app)
    for k, v in old_cookie.items():
        stale.cookies.set(k, v)
    assert stale.get("/api/auth/me").status_code == 401
    assert do_login(app, email, temp)[1].status_code == 401
    assert do_login(app, email, "una-clave-nueva-larga")[1].status_code == 200


def test_temporary_password_expires(app):
    from app.auth import sessions
    from app.db.models import User
    from app.db.session import session_scope

    admin = auth_client(app, "admin", reauth=True)
    r = admin.post("/api/users", json={"email": f"vence-{os.urandom(4).hex()}@example.com"})
    uid, temp = r.json()["user"]["id"], r.json()["temporary_password"]
    with session_scope() as db:
        u = db.get(User, uid)
        u.temp_password_expires_at = sessions.now() - timedelta(minutes=1)
        email = u.email
    assert do_login(app, email, temp)[1].status_code == 401


def test_logout_revokes(app):
    u = make_user("user")
    c, _ = do_login(app, u.email)
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_writes_need_origin_app_header_and_csrf(app):
    u = make_user("user")
    token = session_for(u)
    from fastapi.testclient import TestClient

    from app.auth import sessions

    def client(**drop):
        c = login_headers(TestClient(app), token)
        for h in drop:
            c.headers.pop(h.replace("_", "-"), None)
        return c

    assert client().post("/api/jobs/999999/cancel").status_code == 404  # todo correcto: pasa la guardia
    assert client(Origin=1).post("/api/jobs/999999/cancel").status_code == 403
    assert client(X_Requested_With=1).post("/api/jobs/999999/cancel").status_code == 403
    assert client(X_CSRF_Token=1).post("/api/jobs/999999/cancel").json()["code"] == "CSRF_INVALID"
    bad = client()
    bad.headers["X-CSRF-Token"] = sessions.csrf_for("otro-token")
    assert bad.post("/api/jobs/999999/cancel").status_code == 403
    evil = client()
    evil.headers["Origin"] = "http://localhost:3000.evil.example"
    assert evil.post("/api/jobs/999999/cancel").status_code == 403


def test_admin_writes_need_reauth(app):
    admin = auth_client(app, "admin")
    r = admin.post("/api/users", json={"email": f"r-{os.urandom(4).hex()}@example.com"})
    assert r.status_code == 409 and r.json()["code"] == "REAUTH_REQUIRED"
    assert admin.post("/api/auth/reauthenticate", json={"password": "mala-contraseña-1"}).status_code == 401
    assert admin.post("/api/auth/reauthenticate", json={"password": TEST_PASSWORD}).status_code == 200
    assert admin.post("/api/users", json={"email": f"r-{os.urandom(4).hex()}@example.com"}).status_code == 200


def test_patch_rejects_email_unknown_and_bad_role(app):
    admin = auth_client(app, "admin", reauth=True)
    target = make_user("user")
    for body in ({"email": "otro@example.com"}, {"foo": 1}, {"role": "root"}):
        r = admin.patch(f"/api/users/{target.id}", json=body)
        assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"
    dup = admin.post("/api/users", json={"email": target.email})
    assert dup.status_code == 409 and dup.json()["code"] == "EMAIL_TAKEN"


def test_role_change_deactivation_and_reset_revoke_sessions(app):
    admin = auth_client(app, "admin", reauth=True)
    for change in ({"role": "admin"}, {"active": False}, None):
        target = make_user("user")
        victim = auth_client(app, user=target)
        assert victim.get("/api/auth/me").status_code == 200
        if change is None:
            r = admin.post(f"/api/users/{target.id}/reset-password")
            assert r.status_code == 200 and r.json()["user"]["must_change_password"]
        else:
            assert admin.patch(f"/api/users/{target.id}", json=change).status_code == 200
        assert victim.get("/api/auth/me").status_code == 401, change


def test_last_admin_is_protected(app):
    from sqlalchemy import update

    from app.db.models import User
    from app.db.session import session_scope

    a1 = auth_client(app, "admin", reauth=True)
    other = make_user("admin")
    # deja solo dos admins activos: a1 y other
    with session_scope() as db:
        db.execute(update(User).where(User.role == "admin", User.id.not_in([a1.user.id, other.id]))
                   .values(active=False))
    assert a1.patch(f"/api/users/{other.id}", json={"role": "user"}).status_code == 200
    # ahora a1 es el único admin activo: nadie puede degradarlo ni desactivarlo (ni él mismo)
    for body in ({"role": "user"}, {"active": False}):
        r = a1.patch(f"/api/users/{a1.user.id}", json=body)
        assert r.status_code == 409
    from app.auth.errors import ApiError
    from app.auth.users import guarded_update

    with session_scope() as db:
        me = db.get(User, a1.user.id)
        with pytest.raises(ApiError) as e:
            guarded_update(db, me, {"active": False})
        assert e.value.code == "LAST_ADMIN"
    assert a1.post(f"/api/users/{a1.user.id}/reset-password").status_code == 409


def test_last_admin_concurrent_demotions(app):
    """Dos admins se degradan el uno al otro a la vez: como mucho uno de los dos cambios se aplica."""
    import threading

    from sqlalchemy import func, select, update

    from app.auth.errors import ApiError
    from app.auth.users import guarded_update
    from app.db.models import User
    from app.db.session import session_scope

    a, b = make_user("admin"), make_user("admin")
    with session_scope() as db:
        db.execute(update(User).where(User.role == "admin", User.id.not_in([a.id, b.id])).values(active=False))
    barrier = threading.Barrier(2)
    results = []

    def demote(uid):
        barrier.wait()
        try:
            with session_scope() as db:
                guarded_update(db, db.get(User, uid), {"role": "user"})
            results.append("ok")
        except ApiError as e:
            results.append(e.code)

    ts = [threading.Thread(target=demote, args=(uid,)) for uid in (a.id, b.id)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(results) == ["LAST_ADMIN", "ok"]
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.active)) == 1


def test_user_cannot_manage_accounts(app):
    c = auth_client(app, "user")
    assert c.get("/api/users").status_code == 403
    assert c.post("/api/users", json={"email": "x@example.com"}).status_code == 403
    assert c.post("/api/auth/reauthenticate", json={"password": TEST_PASSWORD}).status_code == 403


def test_recover_cli(app, capsys):
    from app.cli import main
    from app.db.models import User
    from app.db.session import session_scope

    u = make_user("user", active=False)
    main(["auth-recover", "--email", u.email])
    temp = capsys.readouterr().out.strip().splitlines()[-1]
    with session_scope() as db:
        row = db.get(User, u.id)
        assert row.role == "admin" and row.active and row.must_change_password
    _, r = do_login(app, u.email, temp)
    assert r.status_code == 200 and r.json()["session"]["kind"] == "restricted"
