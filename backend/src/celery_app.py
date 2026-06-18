"""
Configuración central de Celery.

Define la aplicación Celery, configura Redis como broker/backend,
y registra el beat schedule para tareas periódicas.

Arranque (worker + beat):
    celery -A src.celery_app worker --beat --loglevel=info --pool=solo

Arranque separado (recomendado en producción):
    celery -A src.celery_app worker --loglevel=info --pool=solo
    celery -A src.celery_app beat --loglevel=info
"""

import logging
from celery import Celery

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "aiuken",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Beat Schedule: tareas periódicas ──

celery_app.conf.beat_schedule = {
    "sync-emails-every-5-minutes": {
        "task": "src.tasks.sync_task.sync_emails_task",
        "schedule": settings.imap_poll_interval_minutes * 60,  # segundos
        "options": {"expires": 60 * 4},  # si la tarea anterior no ha terminado, saltar
    },
}

# Auto-descubrimiento de tareas registradas con @celery_app.task
celery_app.autodiscover_tasks(["src.tasks"])
