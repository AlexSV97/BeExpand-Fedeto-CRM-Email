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

    # ── OpenRouter (IA cloud) ──
    openrouter_api_key: str = ""
    """API key de OpenRouter.
    Vacío = usa Ollama local como fallback."""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/owl-alpha"
    """Modelo para el Analyzer (extracción estructurada).
    openrouter/owl-alpha — gratuito, servido por OpenRouter, sin rate limits de terceros.
    Necesita más capacidad → modelo grande (1.33T MoE)."""
    openrouter_chat_model: str = "openai/gpt-oss-20b:free"
    """Modelo para LLMClassifier y chat (debe ser RÁPIDO y DISTINTO proveedor).
    gpt-oss-20b: OpenInference, proveedor distinto a Owl Alpha (Stealth).
    Evita contención de rate limits con el Analyzer."""
    """Modelo para chat contextual y onboarding."""
    openrouter_timeout: int = 120
    """Timeout para llamadas a OpenRouter (segundos)."""

    # ── BERT fine-tuneado (DistilBERT + ONNX Runtime) ──
    bert_model_path: str = ""
    """Ruta al directorio del modelo BERT fine-tuneado local.
    Vacío = usar ruta por defecto (backend/src/classifier/model-onnx/).
    Útil para sincronizar el modelo vía Dropbox/OneDrive:
        BERT_MODEL_PATH=D:/Dropbox/BeExpand/bert-model
    """
    bert_onnx_model_id: str = "AlexSV97/beexpand-bert-crm"
    """Repo ID del modelo ONNX en HuggingFace Hub para descarga automática.
    BERT ONNX se descarga desde hub si no hay modelo local.
    Requiere HUGGINGFACE_TOKEN configurado.
    El modelo se sirve desde: huggingface.co/AlexSV97/beexpand-bert-crm/tree/main/onnx/"""

    # ── HuggingFace Hub (credenciales para descarga de modelos) ──
    huggingface_token: str = ""
    """Token de HuggingFace para descargar modelo BERT ONNX fine-tuneado privado.
    Necesario en producción (Render), donde el modelo local no está disponible.
    El modelo se descarga automáticamente al arrancar si no existe localmente.
    Token de solo lectura vale, se crea en: https://huggingface.co/settings/tokens
    """

    # ── WhatsApp Business (alertas de correos urgentes) ──
    whatsapp_access_token: str = ""
    """Token de acceso permanente de Meta WhatsApp Cloud API. Vacío = desactivado.
    Se genera en: business.facebook.com → WhatsApp → API Setup."""
    whatsapp_phone_number_id: str = ""
    """ID del número de teléfono emisor en WhatsApp Business API.
    Aparece en la misma página que el token."""
    whatsapp_to_phone: str = ""
    """Número de teléfono destinatario en formato internacional sin + (ej: 34600123456).
    Vacío = desactivado."""
    whatsapp_min_urgency: str = "alta"
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
