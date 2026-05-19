"""
Tarea Celery para sincronización periódica de correos vía IMAP.

Ejecuta sync_emails() cada N minutos según el beat schedule.
La función sync_emails() es async, así que usamos asyncio.run() como puente
(Celery worker no tiene event loop en curso).
"""

import asyncio
import logging

from src.celery_app import celery_app
from src.email_processor.fetcher import sync_emails
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.tasks.sync_task.sync_emails_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_emails_task(self) -> dict:
    """
    Tarea periódica: sincroniza correos UNSEEN desde Gmail vía IMAP.

    Se ejecuta cada imap_poll_interval_minutes (por defecto 5 min)
    definido en el beat schedule de celery_app.

    Returns:
        Dict con resumen: connected, fetched, processed, errors, etc.
    """
    logger.info("🚀 [Auto-Sync] Iniciando sincronización periódica de correos...")

    try:
        # sync_emails() es async — ejecutamos con asyncio.run() desde el worker síncrono
        result = asyncio.run(sync_emails())

        processed = result.get("processed", 0)
        errors = result.get("errors", 0)
        fetched = result.get("fetched", 0)

        logger.info(
            "✅ [Auto-Sync] Completada: %d encontrados, %d procesados, %d errores",
            fetched,
            processed,
            errors,
        )

        if errors > 0 and processed == 0:
            logger.warning("⚠️ [Auto-Sync] Todos los emails terminaron en error")

        return result

    except Exception as exc:
        logger.error("❌ [Auto-Sync] Error en sincronización: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
