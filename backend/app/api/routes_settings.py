"""Ajustes de traducción editables desde la web. La llave de DeepSeek nunca se devuelve completa."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import runtime_settings
from app.worker import friendly_error

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsIn(BaseModel):
    provider: str | None = None
    deepseek_api_key: str | None = None
    deepseek_model: str | None = None
    deepseek_thinking: str | None = None
    claude_model: str | None = None
    claude_concurrency: int | None = None
    deepseek_concurrency: int | None = None


@router.get("/settings")
def get_settings_view():
    return runtime_settings.load().public()


@router.put("/settings")
def save_settings(body: SettingsIn):
    try:
        return runtime_settings.update(body.model_dump(exclude_none=True)).public()
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/settings/test")
def test_settings():
    rs = runtime_settings.load()
    try:
        sample = runtime_settings.test_connection(rs)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "provider": rs.provider, "message": friendly_error(e)}
    return {"ok": True, "provider": rs.provider, "message": f"Conexión correcta. Prueba: «{sample}»"}
