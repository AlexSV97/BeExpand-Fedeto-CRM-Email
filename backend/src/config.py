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

    # ── OpenRouter (IA cloud vía InsForge AI Gateway) ──
    openrouter_api_key: str = ""
    """API key de OpenRouter (gestionada desde InsForge Cloud).
    Vacío = usa Ollama local como fallback."""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "qwen/qwen2.5-7b-instruct"
    """Modelo por defecto para analizadores y clasificadores en OpenRouter.
    qwen2.5-7b-instruct — excelente relación calidad/precio en OpenRouter."""
    openrouter_chat_model: str = "qwen/qwen2.5-7b-instruct"
    """Modelo para chat contextual y onboarding."""
    openrouter_timeout: int = 120
    """Timeout para llamadas a OpenRouter (segundos)."""

    # ── Ollama (IA local) — FALLBACK si no hay OpenRouter ──
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: int = 180

    # ── Chat contextual y clasificador LLM ──
    chat_model: str = "qwen2.5:7b"
    """Modelo usado por el clasificador LLM y el chat de onboarding.
    qwen2.5:7b proporciona clasificación fiable sin los timeouts de hermes3:8b."""
    chat_timeout: int = 300
    # ── BERT (modelo fine-tuned) ──
    bert_model_path: str = ""
    """Ruta al directorio del modelo BERT fine-tuneado.
    Vacío = usar ruta por defecto (backend/src/classifier/model/).
    Útil para sincronizar el modelo vía Dropbox/OneDrive:
        BERT_MODEL_PATH=D:/Dropbox/BeExpand/bert-model
    """

    # ── Telegram (alertas de correos urgentes) ──
    telegram_bot_token: str = ""
    """Token del bot de Telegram (de @BotFather). Vacío = desactivado."""
    telegram_chat_id: str = ""
    """Chat ID del destinatario de las alertas."""
    telegram_min_urgency: str = "alta"
    """Umbral mínimo de urgencia para notificar: alta | media | baja."""

    # ── Redis / Celery ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Auto-sync ──
    sync_interval_seconds: int = 60
    """Intervalo en segundos entre sincronizaciones automáticas de IMAP.
    60 = cada minuto. 0 = desactivado."""

    # ── Entorno ──
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Singleton: la configuración se carga una sola vez."""
    return Settings()
