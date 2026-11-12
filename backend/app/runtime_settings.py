"""Ajustes editables desde la web (modo de traducción, llave de DeepSeek, token de Claude, modelos).

Los valores de `.env` (app.config) son el punto de partida; `data/settings.json` los sobrescribe. El archivo
está fuera del repositorio (data/ en .gitignore), se escribe de forma atómica y con permisos 0600. La llave
completa nunca se devuelve por la API.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.config import get_settings

PROVIDERS = ("deepseek", "claude", "fake")
CLAUDE_MODELS = ("sonnet", "opus")
THINKING_LEVELS = ("disabled", "low", "high", "max")
CLAUDE_TOKEN_PREFIX = "sk-ant-oat"
SECRETS = ("deepseek_api_key", "claude_oauth_token")
_lock = threading.Lock()


@dataclass
class RuntimeSettings:
    provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"
    deepseek_thinking: str = "high"
    claude_model: str = "sonnet"
    claude_concurrency: int = 4
    deepseek_concurrency: int = 10
    # token de `claude setup-token` (suscripción dentro de contenedores); secreto como la llave de DeepSeek
    claude_oauth_token: str = ""

    def public(self) -> dict:
        data = asdict(self)
        key = data.pop("deepseek_api_key")
        data["deepseek_key_set"] = bool(key)
        data["deepseek_key_hint"] = key[-4:] if len(key) >= 8 else ""
        token = data.pop("claude_oauth_token")
        data["claude_token_set"] = bool(token)
        data["claude_token_hint"] = token[-4:] if len(token) >= 8 else ""
        data["claude_available"] = shutil.which(claude_binary()) is not None
        data["claude_auth"] = self.claude_auth()
        return data

    def claude_auth(self) -> str:
        """token = token de setup-token (contenedor) · session = login de Claude Code en este equipo · none."""
        if self.claude_oauth_token:
            return "token"
        if claude_session_path().exists():
            return "session"
        return "none"

    @property
    def concurrency(self) -> int:
        return self.claude_concurrency if self.provider == "claude" else self.deepseek_concurrency

    def configured(self) -> bool:
        if self.provider == "deepseek":
            return bool(self.deepseek_api_key)
        if self.provider == "claude":
            return shutil.which(claude_binary()) is not None and self.claude_auth() != "none"
        return True


def claude_binary() -> str:
    return os.environ.get("CLAUDE_BIN", "claude")


def claude_session_path() -> Path:
    return Path.home() / ".claude" / ".credentials.json"


def settings_path() -> Path:
    return get_settings().data_dir / "settings.json"


def defaults() -> RuntimeSettings:
    st = get_settings()
    return RuntimeSettings(provider="fake" if st.fake_translator else "deepseek",
                           deepseek_api_key=st.deepseek_api_key, deepseek_model=st.deepseek_model,
                           deepseek_thinking=st.deepseek_thinking,
                           deepseek_concurrency=st.translation_concurrency,
                           claude_oauth_token=st.claude_code_oauth_token)


def load() -> RuntimeSettings:
    current = defaults()
    path = settings_path()
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError):
        return current
    names = {f.name for f in fields(RuntimeSettings)}
    for key, value in stored.items():
        if key in names:
            setattr(current, key, value)
    return current


def validate(rs: RuntimeSettings) -> None:
    if rs.provider not in PROVIDERS:
        raise ValueError("Modo de traducción no válido")
    if rs.claude_model not in CLAUDE_MODELS:
        raise ValueError("Modelo de Claude no válido")
    if rs.deepseek_thinking not in THINKING_LEVELS:
        raise ValueError("Nivel de razonamiento no válido")
    for name in ("claude_concurrency", "deepseek_concurrency"):
        value = getattr(rs, name)
        if not isinstance(value, int) or not 1 <= value <= 32:
            raise ValueError("La concurrencia debe estar entre 1 y 32")
    if rs.claude_oauth_token and not rs.claude_oauth_token.startswith(CLAUDE_TOKEN_PREFIX):
        raise ValueError("El token de Claude no es válido: debe ser el que imprime 'claude setup-token' (sk-ant-oat…)")


def update(changes: dict) -> RuntimeSettings:
    """Aplica cambios parciales. Una llave vacía o ausente conserva la actual."""
    with _lock:
        current = load()
        names = {f.name for f in fields(RuntimeSettings)}
        for key, value in changes.items():
            if key not in names or value is None:
                continue
            if key in SECRETS:
                value = str(value).strip()
                if not value:
                    continue
            setattr(current, key, value)
        validate(current)
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".json")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as fh:
                json.dump(asdict(current), fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return current


def make_translator(rs: RuntimeSettings | None = None, prompts: dict | None = None, effort: str | None = None):
    """Crea el traductor del modo elegido. prompts/effort: variantes del playground (producción no los usa)."""
    from app.pipeline.translate import ClaudeCLITranslator, DeepSeekTranslator, FakeTranslator

    rs = rs or load()
    if rs.provider == "fake":
        return FakeTranslator()
    if rs.provider == "claude":
        return ClaudeCLITranslator(model=rs.claude_model, binary=claude_binary(),
                                   oauth_token=rs.claude_oauth_token, prompts=prompts, effort=effort)
    st = get_settings()
    return DeepSeekTranslator(rs.deepseek_api_key, rs.deepseek_model, st.deepseek_base_url,
                              thinking=rs.deepseek_thinking, prompts=prompts)


def test_connection(rs: RuntimeSettings | None = None) -> str:
    """Llamada real mínima con el modo elegido. Devuelve un texto de confirmación o lanza la excepción."""
    rs = rs or load()
    translator = make_translator(rs)
    out = translator.translate_batch([{"id": "t1", "type": "body", "text": "The Sun enters Aries."}], {})
    text = (out.get("t1") or {}).get("translation", "")
    if not text:
        raise RuntimeError("El modelo respondió sin traducción")
    return text
