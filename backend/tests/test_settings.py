"""Ajustes editables (modo de traducción y llave) y su API."""
import json
import stat

import pytest

from app import runtime_settings as rsmod
from app.pipeline.translate import ClaudeCLITranslator, DeepSeekTranslator, FakeTranslator

KEY = "sk-test-0123456789abcd"


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(rsmod, "settings_path", lambda: path)
    monkeypatch.setattr(rsmod, "defaults", lambda: rsmod.RuntimeSettings(provider="deepseek", deepseek_api_key=""))
    return path


def test_update_persists_and_keeps_key(store):
    rsmod.update({"provider": "deepseek", "deepseek_api_key": KEY})
    assert stat.S_IMODE(store.stat().st_mode) == 0o600
    rsmod.update({"provider": "claude", "deepseek_api_key": ""})  # vacía = conservar
    rs = rsmod.load()
    assert rs.provider == "claude" and rs.deepseek_api_key == KEY
    assert json.loads(store.read_text())["provider"] == "claude"


def test_public_never_exposes_key(store):
    data = rsmod.update({"deepseek_api_key": KEY}).public()
    assert KEY not in json.dumps(data)
    assert data["deepseek_key_set"] is True and data["deepseek_key_hint"] == "abcd"


def test_invalid_values_rejected(store):
    with pytest.raises(ValueError):
        rsmod.update({"provider": "gpt"})
    with pytest.raises(ValueError):
        rsmod.update({"claude_model": "haiku-9"})
    assert not store.exists()


def test_factory(store):
    assert isinstance(rsmod.make_translator(rsmod.RuntimeSettings(provider="fake")), FakeTranslator)
    t = rsmod.make_translator(rsmod.RuntimeSettings(provider="claude", claude_model="opus"))
    assert isinstance(t, ClaudeCLITranslator) and t.cli_model == "opus"
    d = rsmod.make_translator(rsmod.RuntimeSettings(provider="deepseek", deepseek_api_key=KEY))
    assert isinstance(d, DeepSeekTranslator)
    assert rsmod.RuntimeSettings(provider="claude").concurrency == 4


def test_settings_api(store):
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.put("/api/settings", json={"provider": "deepseek", "deepseek_api_key": KEY})
    assert r.status_code == 200 and KEY not in r.text
    assert c.get("/api/settings").json()["deepseek_key_set"] is True
    assert c.put("/api/settings", json={"provider": "nope"}).status_code == 400
    c.put("/api/settings", json={"provider": "fake"})
    r = c.post("/api/settings/test").json()
    assert r["ok"] is True and r["provider"] == "fake"
    assert c.get("/api/health").json()["provider"] == "fake"


TOKEN = "sk-ant-oat01-abcdefghijklmnop-wxyz"


def test_claude_token_secret_and_kept(store):
    data = rsmod.update({"provider": "claude", "claude_oauth_token": TOKEN}).public()
    assert TOKEN not in json.dumps(data)
    assert data["claude_token_set"] is True and data["claude_token_hint"] == "wxyz"
    rsmod.update({"claude_oauth_token": ""})  # vacío = conservar
    assert rsmod.load().claude_oauth_token == TOKEN
    t = rsmod.make_translator(rsmod.load())
    assert isinstance(t, ClaudeCLITranslator) and t.oauth_token == TOKEN


def test_claude_token_prefix_validated(store):
    with pytest.raises(ValueError):
        rsmod.update({"claude_oauth_token": "sk-deepseek-123456"})
    assert not store.exists()


def test_claude_auth_modes(store, tmp_path, monkeypatch):
    creds = tmp_path / "credentials.json"
    monkeypatch.setattr(rsmod, "claude_session_path", lambda: creds)
    assert rsmod.RuntimeSettings(provider="claude").claude_auth() == "none"
    creds.write_text("{}")
    assert rsmod.RuntimeSettings(provider="claude").claude_auth() == "session"
    assert rsmod.RuntimeSettings(provider="claude", claude_oauth_token=TOKEN).claude_auth() == "token"


def test_settings_api_token(store):
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.put("/api/settings", json={"provider": "claude", "claude_oauth_token": TOKEN})
    assert r.status_code == 200 and TOKEN not in r.text
    body = c.get("/api/settings").json()
    assert body["claude_token_set"] is True and body["claude_auth"] == "token" and TOKEN not in json.dumps(body)
    assert c.put("/api/settings", json={"claude_oauth_token": "bad"}).status_code == 400
