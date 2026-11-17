"""Ajustes editables (modo de traducción y llave) y su API."""
import json
import stat

import pytest

from app import runtime_settings as rsmod
from app.pipeline.translate import DeepSeekTranslator, FakeTranslator

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
    rsmod.update({"provider": "fake", "deepseek_api_key": ""})  # vacía = conservar
    rs = rsmod.load()
    assert rs.provider == "fake" and rs.deepseek_api_key == KEY
    assert json.loads(store.read_text())["provider"] == "fake"


def test_public_never_exposes_key(store):
    data = rsmod.update({"deepseek_api_key": KEY}).public()
    assert KEY not in json.dumps(data)
    assert data["deepseek_key_set"] is True and data["deepseek_key_hint"] == "abcd"


def test_invalid_values_rejected(store):
    with pytest.raises(ValueError):
        rsmod.update({"provider": "gpt"})
    with pytest.raises(ValueError):
        rsmod.update({"provider": "claude"})  # el modo de suscripción de Claude ya no existe
    with pytest.raises(ValueError):
        rsmod.update({"deepseek_thinking": "extremo"})
    with pytest.raises(ValueError):
        rsmod.update({"deepseek_model": "gpt-4o"})
    assert not store.exists()


def test_model_aliases(store):
    """El nombre erróneo `deepseek-pro` que ofrecía el playground se lee y se guarda como el ID real."""
    store.write_text(json.dumps({"deepseek_model": "deepseek-pro"}))
    assert rsmod.load().deepseek_model == "deepseek-v4-pro"
    assert rsmod.update({"deepseek_model": "deepseek-v4-flash"}).deepseek_model == "deepseek-flash"
    assert rsmod.load().public()["deepseek_models"] == list(rsmod.DEEPSEEK_MODELS)


def test_old_claude_settings_fall_back_to_deepseek(store):
    """Un settings.json guardado con el modo Claude se lee como DeepSeek y sin el token."""
    store.write_text(json.dumps({"provider": "claude", "claude_model": "opus", "claude_oauth_token": "sk-ant-oat01-x",
                                 "deepseek_api_key": KEY}))
    rs = rsmod.load()
    assert rs.provider == "deepseek" and rs.deepseek_api_key == KEY and not hasattr(rs, "claude_oauth_token")
    rsmod.update({"deepseek_thinking": "low"})
    assert "claude" not in store.read_text()  # al guardar desaparecen las claves viejas


def test_factory(store):
    assert isinstance(rsmod.make_translator(rsmod.RuntimeSettings(provider="fake")), FakeTranslator)
    d = rsmod.make_translator(rsmod.RuntimeSettings(provider="deepseek", deepseek_api_key=KEY))
    assert isinstance(d, DeepSeekTranslator)
    assert rsmod.RuntimeSettings(deepseek_concurrency=7).concurrency == 7


def test_settings_api(store):
    from .conftest import admin_client

    from app.main import app

    c = admin_client(app)
    r = c.put("/api/settings", json={"provider": "deepseek", "deepseek_api_key": KEY})
    assert r.status_code == 200 and KEY not in r.text
    assert c.get("/api/settings").json()["deepseek_key_set"] is True
    assert c.put("/api/settings", json={"provider": "nope"}).status_code == 400
    c.put("/api/settings", json={"provider": "fake"})
    r = c.post("/api/settings/test").json()
    assert r["ok"] is True and r["provider"] == "fake"
    assert c.get("/api/health").json()["provider"] == "fake"
