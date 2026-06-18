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


async def _run_sla_scan_once(session_factory=None, ticket_source=None) -> int:
    """Ejecuta un único scan de alertas SLA (SLA-05). Devuelve nº de alertas nuevas.

    Deps inyectables para test: ``session_factory`` (por defecto el de la app) y
    ``ticket_source`` (callable async → list[Ticket]; por defecto resuelve de OTRS
    o tickets de demostración, igual que el War Room).
    """
    from src.services.sla_alerts import SlaAlertService
    from src.services.ticket_lifecycle import TicketLifecycleService
    from src.notifiers.telegram import TelegramNotifier

    session_factory = session_factory or async_session_factory

    if ticket_source is not None:
        tickets = await ticket_source()
    else:
        from src.api.routers.soc import _resolve_tickets_with_mode
        from src.integrations.otrs_znuny.settings import OtrsZnunySettings
        from src.integrations.otrs_znuny.client import OtrsZnunyClient

        otrs = OtrsZnunyClient() if OtrsZnunySettings().is_configured else None
        try:
            tickets, _mode = await _resolve_tickets_with_mode(otrs, 25)
        finally:
            if otrs is not None:
                await otrs.close()

    async with session_factory() as session:
        svc = SlaAlertService(session, TicketLifecycleService(), notifier=TelegramNotifier())
        generated = await svc.scan(tickets)
        return len(generated)


async def _sla_alert_loop():
    """Bucle de fondo que ejecuta el scan de alertas SLA cada N segundos (SLA-05).

    Desactivado por defecto (``sla_alert_scan_interval_seconds=0``). El scan
    sigue disponible on-demand vía endpoint.
    """
    settings = get_settings()
    interval = settings.sla_alert_scan_interval_seconds
    if interval <= 0:
        logger.info("SLA alert scan desactivado (sla_alert_scan_interval_seconds=%d)", interval)
        return

    logger.info("SLA alert scan iniciado — cada %d segundos", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            generated = await _run_sla_scan_once()
            if generated:
                logger.info("SLA alert scan: %d alerta(s) generada(s)", generated)
        except asyncio.CancelledError:
            logger.info("SLA alert scan: bucle cancelado")
            break
        except Exception as exc:
            logger.error("SLA alert scan: error inesperado: %s", exc)


async def seed_queues() -> None:
    """Sincroniza colas desde OTRS y garantiza la topología por defecto.

    ``init_db`` crea la tabla ``queues`` (create_all) pero el seed de la
    migración Alembic no se ejecuta en el deploy; esto intenta primero la
    sincronización viva con OTRS y luego deja la topología/colas de negocio
    mínimas de forma idempotente.
    """
    from src.services.queue_sync import QueueSyncService

    try:
        async with async_session_factory() as session:
            sync_svc = QueueSyncService(session)
            await sync_svc.sync_from_otrs()
            await sync_svc.seed_defaults()
    except Exception as exc:  # noqa: BLE001 — no bloquear el arranque
        logger.warning("seed_queues: no se pudo sembrar la topología de colas (%s)", exc)


async def seed_knowledge_vault() -> None:
    """Carga el vault de conocimiento desde snapshot y lo enriquece con tickets cerrados.

    Si OTRS/Znuny está configurado, toma los tickets disponibles y los ingiere
    en el vault antes de persistir el snapshot actualizado.
    """
    from src.api.routers.soc import _resolve_tickets_with_mode, _seed_knowledge_documents
    from src.integrations.otrs_znuny.client import OtrsZnunyClient
    from src.integrations.otrs_znuny.settings import OtrsZnunySettings
    from src.llm_client import LLMClient
    from src.services.knowledge_vault import KnowledgeVaultService
    from src.services.knowledge_vault_store import load_knowledge_vault_snapshot, save_knowledge_vault_snapshot

    llm_client = LLMClient(use_chat_model=True)
    seed_docs = _seed_knowledge_documents()

    async with async_session_factory() as session:
        snapshot = await load_knowledge_vault_snapshot(session)
        if snapshot:
            vault = KnowledgeVaultService.from_snapshot(snapshot, llm_client=llm_client)
        else:
            vault = KnowledgeVaultService(documents=seed_docs, llm_client=llm_client)

        existing_ids = {doc.id for doc in vault.documents}
        for doc in seed_docs:
            if doc.id not in existing_ids:
                vault.add_document_with_embedding(doc)

        otrs = OtrsZnunyClient() if OtrsZnunySettings().is_configured else None
        try:
            tickets, _mode = await _resolve_tickets_with_mode(otrs, 50)
            await vault.ingest_closed_tickets(tickets, embed=True)
        finally:
            if otrs is not None:
                await otrs.close()

        await save_knowledge_vault_snapshot(session, vault)


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
    if getattr(settings, "admin_password", "") == "CHANGE_ME_ADMIN_PASSWORD":
        warnings.append("ADMIN_PASSWORD sigue siendo el valor por defecto (CHANGE_ME_ADMIN_PASSWORD)")
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
    await seed_queues()
    await seed_knowledge_vault()
    await _check_production_settings()

    task = asyncio.create_task(_auto_sync_loop())
    _background_tasks.append(task)
    _background_tasks.append(asyncio.create_task(_sla_alert_loop()))
    yield

    for t in _background_tasks:
        t.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()


app = FastAPI(
    title="Aiuken SOC API",
    description="API de clasificación y gestión de correos para Aiuken SOC",
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
    "https://aiuken-frontend.onrender.com"
)
_cors_origins_str = os.getenv("CORS_ORIGINS", _cors_default)
_cors_origins_list = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
async def root():
    """Endpoint de bienvenida (health check)."""
    return {
        "app": "Aiuken SOC",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/api/v1/health")
async def health():
    """Health check with real per-dependency probes."""
    from sqlalchemy import text
    from src.config import get_settings
    from src.db.session import async_session_factory
    from src.integrations.otrs_znuny import OtrsZnunyClient, OtrsZnunySettings
    from src.llm_client import LLMClient

    import asyncio

    settings = get_settings()

    async def _check_db() -> dict:
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _check_otrs() -> dict:
        otrs_settings = OtrsZnunySettings()
        if not otrs_settings.is_configured:
            return {"status": "not_configured", "message": "OTRS_ZNUNY_BASE_URL or OTRS_ZNUNY_API_TOKEN not set"}
        client = OtrsZnunyClient(settings=otrs_settings)
        try:
            ok = await client.health_check()
            await client.close()
            if ok:
                return {"status": "ok"}
            return {"status": "error", "message": "OTRS API returned error status"}
        except Exception as e:
            await client.close()
            return {"status": "error", "message": str(e)}

    async def _check_ai() -> dict:
        try:
            llm = LLMClient(use_chat_model=True)
            result = await llm.check_health()
            return {"status": "ok" if result else "error", "message": None if result else "AI model not responding"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    db_result, otrs_result, ai_result = await asyncio.gather(
        _check_db(), _check_otrs(), _check_ai(), return_exceptions=True
    )

    services = {
        "database": db_result if not isinstance(db_result, BaseException) else {"status": "error", "message": str(db_result)},
        "otrs": otrs_result if not isinstance(otrs_result, BaseException) else {"status": "error", "message": str(otrs_result)},
        "ai": ai_result if not isinstance(ai_result, BaseException) else {"status": "error", "message": str(ai_result)},
    }

    all_ok = all(s.get("status") == "ok" for s in services.values())
    overall = "ok" if all_ok else "degraded"

    return {
        "status": overall,
        "services": services,
        "app": "Aiuken SOC",
        "version": "0.1.0",
    }
