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

    # ── IMAP (Gmail) ──
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    imap_email: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_poll_interval_minutes: int = 5
    imap_folder_map: dict[str, str] = {
        "cliente": "INBOX/Clientes",
        "lead": "INBOX/Leads",
        "proveedor": "INBOX/Proveedores",
    }
    """Mapa categoría → carpeta IMAP destino.
    Los emails clasificados se mueven a estas carpetas tras procesarse.
    Las categorías no incluidas (ej: nulo) se quedan en INBOX.
    Para desactivar, dejar diccionario vacío: {}"""

    # ── VTiger ──
    vtiger_url: str = ""
    vtiger_token: str = ""
    vtiger_username: str = ""

    # ── Ollama (IA local) ──
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "hermes3:8b"
    """Modelo usado por clasificadores y analizadores (precisión crítica)."""
    ollama_timeout: int = 30

    # ── Chat contextual ──
    chat_model: str = "qwen2.5:3b"
    """Modelo usado por el chat de onboarding (prioriza velocidad en CPU).
    qwen2.5:3b (~1.9 GB) es más rápido de cargar que phi4-mini (~2.5 GB)
    y suficiente para respuestas guiadas."""
    chat_timeout: int = 120

    # ── BERT (modelo fine-tuned) ──
    bert_model_path: str = ""
    """Ruta al directorio del modelo BERT fine-tuneado.
    Vacío = usar ruta por defecto (backend/src/classifier/model/).
    Útil para sincronizar el modelo vía Dropbox/OneDrive:
        BERT_MODEL_PATH=D:/Dropbox/BeExpand/bert-model
    """

    # ── Redis / Celery ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Entorno ──
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Singleton: la configuración se carga una sola vez."""
    return Settings()
