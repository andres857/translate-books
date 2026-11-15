"""Ajustes editables desde la web (modo de traducción, llave y modelo de DeepSeek).

Los valores de `.env` (app.config) son el punto de partida; `data/settings.json` los sobrescribe. El archivo
está fuera del repositorio (data/ en .gitignore), se escribe de forma atómica y con permisos 0600. La llave
completa nunca se devuelve por la API.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.config import get_settings

PROVIDERS = ("deepseek", "fake")
THINKING_LEVELS = ("disabled", "low", "high", "max")
SECRETS = ("deepseek_api_key",)
_lock = threading.Lock()


@dataclass
class RuntimeSettings:
    provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"
    deepseek_thinking: str = "high"
    deepseek_concurrency: int = 10

    def public(self) -> dict:
        data = asdict(self)
        key = data.pop("deepseek_api_key")
        data["deepseek_key_set"] = bool(key)
        data["deepseek_key_hint"] = key[-4:] if len(key) >= 8 else ""
        return data

    @property
    def concurrency(self) -> int:
        return self.deepseek_concurrency

    def configured(self) -> bool:
        if self.provider == "deepseek":
            return bool(self.deepseek_api_key)
        return True


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
        if key in names:  # claves de modos retirados (p. ej. claude_*) se ignoran
            setattr(current, key, value)
    if current.provider not in PROVIDERS:  # ajustes guardados con el modo de suscripción de Claude, ya retirado
        current.provider = "deepseek"
    return current


def validate(rs: RuntimeSettings) -> None:
    if rs.provider not in PROVIDERS:
        raise ValueError("Modo de traducción no válido")
    if rs.deepseek_thinking not in THINKING_LEVELS:
        raise ValueError("Nivel de razonamiento no válido")
    value = rs.deepseek_concurrency
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


def make_translator(rs: RuntimeSettings | None = None, prompts: dict | None = None):
    """Crea el traductor del modo elegido. prompts: borradores del playground (producción no los usa)."""
    from app.pipeline.translate import DeepSeekTranslator, FakeTranslator

    rs = rs or load()
    if rs.provider == "fake":
        return FakeTranslator()
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
