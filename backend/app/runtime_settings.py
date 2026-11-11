"""Ajustes editables desde la web (modo de traducción, llave de DeepSeek, modelos).

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

    def public(self) -> dict:
        data = asdict(self)
        key = data.pop("deepseek_api_key")
        data["deepseek_key_set"] = bool(key)
        data["deepseek_key_hint"] = key[-4:] if len(key) >= 8 else ""
        data["claude_available"] = shutil.which(claude_binary()) is not None
        return data

    @property
    def concurrency(self) -> int:
        return self.claude_concurrency if self.provider == "claude" else self.deepseek_concurrency

    def configured(self) -> bool:
        if self.provider == "deepseek":
            return bool(self.deepseek_api_key)
        if self.provider == "claude":
            return shutil.which(claude_binary()) is not None
        return True


def claude_binary() -> str:
    return os.environ.get("CLAUDE_BIN", "claude")


def settings_path() -> Path:
    return get_settings().data_dir / "settings.json"


def defaults() -> RuntimeSettings:
    st = get_settings()
    return RuntimeSettings(provider="fake" if st.fake_translator else "deepseek",
                           deepseek_api_key=st.deepseek_api_key, deepseek_model=st.deepseek_model,
                           deepseek_thinking=st.deepseek_thinking,
                           deepseek_concurrency=st.translation_concurrency)


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


def update(changes: dict) -> RuntimeSettings:
    """Aplica cambios parciales. Una llave vacía o ausente conserva la actual."""
    with _lock:
        current = load()
        names = {f.name for f in fields(RuntimeSettings)}
        for key, value in changes.items():
            if key not in names or value is None:
                continue
            if key == "deepseek_api_key":
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


def make_translator(rs: RuntimeSettings | None = None):
    """Crea el traductor del modo elegido."""
    from app.pipeline.translate import ClaudeCLITranslator, DeepSeekTranslator, FakeTranslator

    rs = rs or load()
    if rs.provider == "fake":
        return FakeTranslator()
    if rs.provider == "claude":
        return ClaudeCLITranslator(model=rs.claude_model, binary=claude_binary())
    st = get_settings()
    return DeepSeekTranslator(rs.deepseek_api_key, rs.deepseek_model, st.deepseek_base_url,
                              thinking=rs.deepseek_thinking)


def test_connection(rs: RuntimeSettings | None = None) -> str:
    """Llamada real mínima con el modo elegido. Devuelve un texto de confirmación o lanza la excepción."""
    rs = rs or load()
    translator = make_translator(rs)
    out = translator.translate_batch([{"id": "t1", "type": "body", "text": "The Sun enters Aries."}], {})
    text = (out.get("t1") or {}).get("translation", "")
    if not text:
        raise RuntimeError("El modelo respondió sin traducción")
    return text
