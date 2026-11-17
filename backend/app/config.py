"""Configuración central (lee .env). La llave de DeepSeek nunca se guarda en BD ni se expone."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    data_dir: Path = Path("./data")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_vision_model: str = "deepseek-flash"
    # razonamiento al traducir: disabled | low | high | max (high = máxima calidad, más lento)
    deepseek_thinking: str = "high"

    # traductor falso (sin API) para probar la maquetación y la interfaz sin gastar tokens
    fake_translator: bool = False
    # orígenes exactos del navegador: CORS y validación de Origin en escrituras (separados por comas)
    cors_origins: str = "http://localhost:3000"

    # ---- login (ver app/auth). El admin inicial se crea una sola vez si su correo no existe.
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""
    admin_bootstrap_name: str = "Administrador"
    session_max_hours: float = 8
    session_idle_minutes: float = 30
    reauth_minutes: float = 10
    temp_password_hours: float = 24
    # auto = Secure salvo que todos los orígenes sean http://localhost (desarrollo)
    cookie_secure: str = "auto"
    login_window_minutes: float = 15
    login_max_per_ip: int = 10
    login_max_per_email: int = 10
    login_max_global: int = 200
    # IPs o redes (CIDR) de proxies propios, separadas por comas: el frontend Next reenvía /api/* y todas sus
    # peticiones llegan con su IP. Desde ellas la IP del cliente es desconocida (Next no añade
    # X-Forwarded-For), así que el límite por IP no se aplica; siguen el de correo y el total.
    trusted_proxies: str = ""
    # purga (`python -m app.cli purge`): sesiones revocadas o caducadas hace más de N días y eventos de seguridad
    auth_sessions_retention_days: float = 30
    auth_events_retention_days: float = 180

    max_upload_mb: int = 200
    translation_concurrency: int = 10
    translation_batch_chars: int = 3000
    translation_batch_max_segments: int = 40

    # Ajuste de texto: nunca por debajo de estos límites; si no cabe → revisión
    min_font_scale: float = 0.75
    min_font_size_pt: float = 5.5

    # Directorios de fuentes separados por ':' o ';'
    fonts_dirs: str = "./fonts"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_networks(self) -> list:
        import ipaddress

        nets = []
        for item in self.trusted_proxies.split(","):
            if item.strip():
                nets.append(ipaddress.ip_network(item.strip(), strict=False))
        return nets

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure.lower() in ("true", "1", "yes"):
            return True
        if self.cookie_secure.lower() in ("false", "0", "no"):
            return False
        return not all(o.startswith(("http://localhost", "http://127.0.0.1")) for o in self.allowed_origins)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
