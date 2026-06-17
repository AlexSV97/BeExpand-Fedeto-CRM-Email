"""
Punto de entrada de la API REST.

Arranque: uvicorn src.api.main:app --reload
"""

import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.utils.passwords import hash_password
from sqlalchemy import select

from src.api.routers import (
    accounts,
    agents,
    auth,
    chat,
    classification,
    contacts,
    crm,
    dashboard,
    emails,
    invoices,
    knowledge,
    opportunities,
    reporting,
    queues,
    settings,
    sla,
    soc,
    tickets,
)
from src.api.middleware.error_handler import soc_error_handler
from src.config import get_settings
from src.db.models import ReprocessTask, User
from src.db.session import async_session_factory, init_db

_background_tasks: list[asyncio.Task[None]] = []


async def _auto_sync_loop():
    """Bucle infinito que sincroniza correos cada N segundos.

    Se ejecuta como background task y se cancela limpiamente al apagar.
    """
    settings = get_settings()
    interval = settings.sync_interval_seconds
    if interval <= 0:
        logger.info("Auto-sync desactivado (sync_interval_seconds=%d)", interval)
        return

    logger.info("Auto-sync iniciado — cada %d segundos", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            if not settings.imap_email or not settings.imap_password:
                logger.debug("Auto-sync: IMAP no configurado, esperando...")
                continue
            logger.info("Auto-sync: sincronizando correos...")
            from src.email_processor.fetcher import sync_emails
            result = await sync_emails()
            if result.get("error"):
                logger.warning("Auto-sync: %s", result["error"])
            elif result.get("processed", 0) > 0:
                logger.info(
                    "Auto-sync: %d procesados, %d errores",
                    result["processed"],
                    result["errors"],
                )
        except asyncio.CancelledError:
            logger.info("Auto-sync: bucle cancelado")
            break
        except Exception as exc:
            logger.error("Auto-sync: error inesperado: %s", exc)


async def seed_admin():
    """Garantiza que exista un usuario admin con las credenciales configuradas.

    Si el usuario ya existe, sincroniza contraseña, rol y estado para evitar
    quedar bloqueados en entornos donde no hay acceso al dashboard del deploy.
    """
    settings = get_settings()
    if not settings.admin_username or not settings.admin_password:
        logger.info(
            "seed_admin: ADMIN_USERNAME o ADMIN_PASSWORD vacíos — "
            "se omite sincronización de admin por defecto"
        )
        return
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        user = result.scalar_one_or_none()
        hashed_password = hash_password(settings.admin_password)

        if user is None:
            user = User(
                username=settings.admin_username,
                hashed_password=hashed_password,
                role="admin",
                active=True,
                full_name="Administrador",
            )
            session.add(user)
            logger.warning("seed_admin: usuario admin creado/sincronizado: %s", settings.admin_username)
        else:
            user.hashed_password = hashed_password
            user.role = "admin"
            user.active = True
            if not user.full_name:
                user.full_name = "Administrador"
            logger.warning("seed_admin: contraseña admin resincronizada para %s", settings.admin_username)

        await session.commit()


async def _recover_orphan_tasks() -> None:
    """Resetea tareas de reprocess que quedaron 'processing' tras un reinicio."""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(ReprocessTask).where(ReprocessTask.status == "processing")
            )
            orphaned = result.scalars().all()
            if not orphaned:
                return
            now = datetime.now(timezone.utc)
            for t in orphaned:
                t.status = "failed"
                t.error = (
                    "Tarea huérfana por reinicio del servicio. "
                    "Crea un nuevo reprocess para reintentar."
                )
                t.completed_at = now
            await db.commit()
            logger.warning(
                "Recuperadas %d tareas de reprocess huérfanas (processing failed)",
                len(orphaned),
            )
    except Exception as exc:
        logger.error("Error recuperando tareas huérfanas: %s", exc)


async def _check_production_settings():
    """Loggea advertencias si se detectan valores por defecto de desarrollo."""
    settings = get_settings()
    logger = logging.getLogger("uvicorn")
    warnings: list[str] = []

    if "dev" in (settings.secret_key or "").lower() or not settings.secret_key:
        warnings.append("SECRET_KEY est� configurada con un valor de desarrollo o vac�o")
    if getattr(settings, "admin_password", "") == "admin123":
        warnings.append("ADMIN_PASSWORD sigue siendo el valor por defecto (admin123)")
    if settings.debug:
        warnings.append("DEBUG mode activado — desactivar en producci�n")

    for w in warnings:
        logger.warning("🔐 PRODUCTION WARNING: %s", w)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: se ejecuta al arrancar y al cerrar la app."""
    logging.basicConfig(level=logging.INFO, force=True)

    await init_db()
    await _recover_orphan_tasks()
    await seed_admin()
    await _check_production_settings()

    task = asyncio.create_task(_auto_sync_loop())
    _background_tasks.append(task)
    yield

    for t in _background_tasks:
        t.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()


app = FastAPI(
    title="BeExpand CRM Email API",
    description="API de clasificación y gestión de correos con integración VTiger",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(emails.router, prefix="/api/v1/emails")
app.include_router(contacts.router, prefix="/api/v1/contacts")
app.include_router(opportunities.router, prefix="/api/v1/opportunities")
app.include_router(classification.router, prefix="/api/v1/classification-history")
app.include_router(crm.router, prefix="/api/v1/crm")
app.include_router(dashboard.router, prefix="/api/v1/dashboard")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(reporting.router, prefix="/api/v1")
app.include_router(queues.router, prefix="/api/v1")
app.include_router(sla.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(soc.router, prefix="/api/v1")

# ── Safe error handler ──────────────────────────────────────────────────────
app.exception_handler(Exception)(soc_error_handler)

# CORS — configurable via CORS_ORIGINS env var (comma-separated)
import os
_cors_default = (
    "http://localhost:5173,"
    "http://localhost:3000,"
    "http://127.0.0.1:5173,"
    "https://beconnect-frontend.onrender.com"
)
_cors_origins_str = os.getenv("CORS_ORIGINS", _cors_default)
_cors_origins_list = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
async def root():
    """Endpoint de bienvenida (health check)."""
    return {
        "app": "BeExpand CRM Email",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/api/v1/health")
async def health():
    """Health check detallado."""
    from src.config import get_settings
    db_url = get_settings().database_url
    db_type = "postgresql" if "postgresql" in db_url else "sqlite"
    return {
        "status": "healthy",
        "database": db_type,
    }