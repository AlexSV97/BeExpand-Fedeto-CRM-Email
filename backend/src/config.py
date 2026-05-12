"""
Configuración centralizada de la aplicación.
Las variables se leen desde .env y se validan con Pydantic.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Base de datos ──
    database_url: str = "sqlite+aiosqlite:///./beexpand.db"

    # ── JWT ──
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 horas

    # ── Admin por defecto ──
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # ── VTiger ──
    vtiger_url: str = ""
    vtiger_token: str = ""
    vtiger_username: str = ""
    vtiger_access_key: str = ""
    vtiger_api_version: str = "v1"

    # ── M3 Feature Flag ──
    m3_enabled: bool = False

    # ── Classification ──
    classification_default_confidence: float = 0.7

    # ── Entorno ──
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Singleton: la configuración se carga una sola vez."""
    return Settings()
