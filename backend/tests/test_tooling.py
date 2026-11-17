"""Herramientas de control: el esquema de las migraciones coincide con los modelos y `count_queries` funciona."""
import os
import subprocess
import sys

import pytest

from .conftest import ROOT, count_queries


def test_alembic_check(tmp_path):
    """Una BD vacía migrada a `head` no tiene operaciones pendientes frente a los modelos (`alembic check`)."""
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'check.db').as_posix()}"}

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=120)

    up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    check = alembic("check")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "No new upgrade operations detected" in check.stdout + check.stderr


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


def test_glossary_list_queries_do_not_grow_with_entries(client):
    """`GET /api/glossary` hace las mismas queries con 1 entrada que con 5 (sin N+1)."""
    import uuid

    tag = uuid.uuid4().hex[:8]

    def add(n):
        r = client.post("/api/glossary", json={"source": f"term-{tag}-{n}", "target": f"término-{n}"})
        assert r.status_code == 200, r.text

    add(0)
    with count_queries() as one:
        assert client.get("/api/glossary").status_code == 200
    for n in range(1, 5):
        add(n)
    with count_queries() as five:
        assert client.get("/api/glossary").status_code == 200
    assert one.count > 0
    assert five.count == one.count, five.statements
