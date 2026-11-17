"""Ajustes de traducción editables desde la web. La llave de DeepSeek nunca se devuelve."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import runtime_settings
from app.api.schemas import SettingsPublic, SettingsTestOut, SettingsUserView
from app.auth.deps import Principal, require_admin, require_user
from app.worker import friendly_error

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsIn(BaseModel):
    provider: str | None = None
    deepseek_api_key: str | None = None
    deepseek_model: str | None = None
    deepseek_thinking: str | None = None
    deepseek_concurrency: int | None = None


@router.get("/settings", response_model=SettingsPublic | SettingsUserView)
def get_settings_view(p: Principal = Depends(require_user)):
    """El admin ve todos los ajustes; el user, solo lo que pinta el rótulo del método (sin pista de la llave)."""
    rs = runtime_settings.load()
    return rs.public() if p.is_admin else rs.method()


@router.put("/settings", response_model=SettingsPublic, dependencies=[Depends(require_admin)])
def save_settings(body: SettingsIn):
    try:
        return runtime_settings.update(body.model_dump(exclude_none=True)).public()
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/settings/test", response_model=SettingsTestOut, dependencies=[Depends(require_admin)])
def test_settings():
    rs = runtime_settings.load()
    try:
        sample = runtime_settings.test_connection(rs)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "provider": rs.provider, "message": friendly_error(e)}
    return {"ok": True, "provider": rs.provider, "message": f"Conexión correcta. Prueba: «{sample}»"}
