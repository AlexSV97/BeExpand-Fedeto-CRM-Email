"""
Punto de entrada de la API REST.

Arranque: uvicorn src.api.main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.hash import bcrypt
from sqlalchemy import select

from src.api.routers import (
    accounts,
    auth,
    chat,
    classification,
    contacts,
    crm,
    dashboard,
    emails,
    opportunities,
)
from src.config import get_settings
from src.db.models import User
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
    """Crea el usuario admin por defecto si no existe."""
    settings = get_settings()
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is None:
            user = User(
                username=settings.admin_username,
                hashed_password=bcrypt.hash(settings.admin_password),
                role="admin",
                active=True,
                full_name="Administrador",
            )
            session.add(user)
            await session.commit()


async def _warmup_chat_model():
    """Precarga el modelo de chat en Ollama para que la 1ª respuesta sea rápida."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.chat_timeout) as client:
            await client.post(
                f"{settings.ollama_url}/api/chat",
                json={
                    "model": settings.chat_model,
                    "messages": [{"role": "user", "content": "warmup"}],
                    "stream": False,
                    "keep_alive": -1,
                },
            )
        logger.info(
            "Chat model %s warm-up OK", settings.chat_model
        )
    except Exception as exc:
        logger.warning(
            "Chat model %s warm-up failed (non-critical): %s",
            settings.chat_model,
            exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: se ejecuta al arrancar y al cerrar la app."""
    # Forzar logging INFO + handler para que se vean los logs del auto-sync
    logging.basicConfig(level=logging.INFO, force=True)

    # Al arrancar: crear tablas si no existen + seed admin + warm-up chat
    await init_db()
    await seed_admin()
    await _warmup_chat_model()

    # Arrancar auto-sync en background
    task = asyncio.create_task(_auto_sync_loop())
    _background_tasks.append(task)

    yield

    # Al cerrar: cancelar background tasks
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

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(emails.router, prefix="/api/v1/emails")
app.include_router(contacts.router, prefix="/api/v1/contacts")
app.include_router(opportunities.router, prefix="/api/v1/opportunities")
app.include_router(classification.router, prefix="/api/v1/classification-history")
app.include_router(crm.router, prefix="/api/v1/crm")
app.include_router(dashboard.router, prefix="/api/v1/dashboard")
app.include_router(chat.router, prefix="/api/v1")

# CORS: en Docker el frontend (nginx) sirve en localhost:5173, en dev Vite en :5173
_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Si hay variable de entorno CORS_ORIGINS, añadir las que vengan
import os
_env_origins = os.getenv("CORS_ORIGINS", "")
if _env_origins:
    _cors_origins.extend(_env_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
