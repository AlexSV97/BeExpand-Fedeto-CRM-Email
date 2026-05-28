"""
Router de correos electrónicos.

GET list con filtros: category, status, date_from/to, skip, limit.
GET /{id} detail que incluye classification_history.
POST /{id}/reprocess — re-clasifica un email existente (asíncrono).
GET /reprocess/tasks/{task_id} — estado de una tarea de reprocesado.
PATCH /{id}/review — revisión manual de categoría por un usuario.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import ClassificationHistory, Contact, Email, ReprocessTask, User
from src.db.session import async_session_factory, get_db

from src.api.deps import get_current_user, pagination_params
from src.api.schemas import EmailDetailResponse, EmailList, EmailResponse
from src.email_processor import sync_emails
from src.orchestrator.context import EmailData
from src.orchestrator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# ── Background task tracking ──────────────────────────────────────────────
_background_tasks: list[asyncio.Task] = []


def _cleanup_task(task: asyncio.Task) -> None:
    """Remove task from tracking list (used as done callback)."""
    try:
        _background_tasks.remove(task)
    except ValueError:
        pass

router = APIRouter(tags=["emails"])

VALID_CATEGORIES = {"cliente", "lead", "proveedor", "nulo"}


class ReviewRequest(BaseModel):
    """Cuerpo de la petición de revisión manual."""
    category: str


@router.post("/sync")
async def sync_imap_emails(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sincroniza correos desde Gmail vía IMAP.
    Busca UNSEEN, parsea, clasifica por reglas y guarda en BD.
    """
    result = await sync_emails(db=db)
    return result


# ── Background reprocess pipeline ─────────────────────────────────────────


async def _update_email_from_context(email: Email, ctx) -> None:
    """Update email fields with Orchestrator context results."""
    email.category = ctx.final_category or email.category
    email.status = "procesado" if ctx.final_category else "pendiente"
    email.processed_at = datetime.now(timezone.utc)
    email.summary = ctx.extracted.summary if ctx.extracted else email.summary
    email.extra_data = {
        "resolution_method": ctx.resolution_method,
        "confidence": ctx.final_confidence,
        "votes": [
            {"agent": v.agent_name, "category": v.category, "confidence": v.confidence}
            for v in ctx.votes
        ],
        "routing": {
            "departments": ctx.routing.departments if ctx.routing else [],
            "persons": ctx.routing.persons if ctx.routing else [],
            "rationale": ctx.routing.rationale if ctx.routing else None,
        },
        "analyzer": {
            "urgency": ctx.extracted.urgency if ctx.extracted else "media",
            "action_required": ctx.extracted.action_required if ctx.extracted else None,
            "tone": ctx.extracted.tone if ctx.extracted else None,
            "company": ctx.extracted.company if ctx.extracted else None,
        },
        "processing_time_ms": ctx.processing_time_ms,
        "suggested_reply": ctx.suggested_reply or "",
    }
    if ctx.final_category in ("lead",):
        email.relevance = "alta"
    elif ctx.final_category == "nulo":
        email.relevance = "baja"
    elif ctx.extracted and ctx.extracted.urgency == "alta":
        email.relevance = "alta"
    else:
        email.relevance = "media"


async def _run_reprocess_background(email_id: str, task_id: str) -> None:
    """Run the full reprocess pipeline in background."""
    try:
        async with async_session_factory() as db:
            # ── Mark task as processing ──
            t_result = await db.execute(
                select(ReprocessTask).where(ReprocessTask.id == task_id)
            )
            task = t_result.scalar_one_or_none()
            if task is None:
                logger.error("Reprocess task %s not found in DB", task_id[:8])
                return
            task.status = "processing"
            await db.commit()

            # ── Load email ──
            e_result = await db.execute(
                select(Email).where(Email.id == email_id)
            )
            email = e_result.scalar_one_or_none()
            if email is None:
                task.status = "failed"
                task.error = "Email not found"
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # ── Build EmailData ──
            email_data = EmailData(
                message_id=email.message_id,
                subject=email.subject or "",
                body_plain=email.body_plain or "",
                body_html=email.body_html,
                sender_name=email.sender_name or email.sender_email.split("@")[0],
                sender_email=email.sender_email,
                recipients=email.recipients or [],
                has_attachments=email.has_attachments,
                received_at=email.received_at,
            )

            # ── Run pipeline ──
            orchestrator = Orchestrator(db=db)
            ctx = await orchestrator.process(email_data, db=db)

            # ── Update email ──
            await _update_email_from_context(email, ctx)

            # ── Update task as completed ──
            task.status = "completed"
            task.result_category = ctx.final_category
            task.result_confidence = ctx.final_confidence
            task.result_resolution = ctx.resolution_method
            task.result_votes = [
                {"agent": v.agent_name, "category": v.category, "confidence": v.confidence}
                for v in ctx.votes
            ]
            task.processing_time_ms = ctx.processing_time_ms
            task.completed_at = datetime.now(timezone.utc)

            await db.commit()

            logger.info(
                "Background reprocess %s ok: %s (%.0f%%) via %s | %.0fms",
                email_id[:8],
                ctx.final_category,
                (ctx.final_confidence or 0) * 100,
                ctx.resolution_method,
                ctx.processing_time_ms or 0,
            )

    except Exception as exc:
        logger.error("Background reprocess %s failed: %s", email_id[:8], exc, exc_info=True)
        try:
            async with async_session_factory() as db:
                t_result = await db.execute(
                    select(ReprocessTask).where(ReprocessTask.id == task_id)
                )
                task = t_result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error = str(exc)
                    task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception as db_err:
            logger.error("Failed to persist reprocess failure: %s", db_err)


# ── Endpoints ──


@router.get("/reprocess/tasks/{task_id}")
async def get_reprocess_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el estado de una tarea de reprocesado asíncrono.

    Devuelve el resultado completo cuando la tarea ha terminado (status=completed),
    o el error si ha fallado (status=failed).
    """
    result = await db.execute(
        select(ReprocessTask).where(ReprocessTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reprocess task not found",
        )
    return {
        "task_id": task.id,
        "email_id": task.email_id,
        "status": task.status,
        "result": {
            "category": task.result_category,
            "confidence": task.result_confidence,
            "resolution": task.result_resolution,
            "votes": task.result_votes,
            "processing_time_ms": task.processing_time_ms,
        }
        if task.status == "completed"
        else None,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.post("/{email_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_email(
    email_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-clasifica un email existente (asíncrono).

    Crea una tarea de reprocesado y lanza el pipeline en background.
    Devuelve 202 Accepted con un task_id para consultar el resultado
    mediante GET /reprocess/tasks/{task_id}.

    Pipeline: Analyzer → 3 clasificadores paralelo → VoteResolver
    → Router → ActionExecutor.
    """
    # 1. Verificar que el email existe
    result = await db.execute(
        select(Email).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    # 2. Crear registro de tarea
    task = ReprocessTask(
        id=str(uuid.uuid4()),
        email_id=email_id,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 3. Lanzar pipeline en background
    bg = asyncio.create_task(_run_reprocess_background(email_id, task.id))
    _background_tasks.append(bg)
    bg.add_done_callback(_cleanup_task)

    logger.info(
        "Reprocess task %s creada para email %s",
        task.id[:8],
        email_id[:8],
    )

    return {
        "status": "accepted",
        "task_id": task.id,
        "email_id": email_id,
    }


@router.get("", response_model=EmailList)
async def list_emails(
    category: str | None = Query(None, description="Filtrar por categoría"),
    status: str | None = Query(None, description="Filtrar por estado"),
    date_from: datetime | None = Query(None, description="Fecha inicio (ISO)"),
    date_to: datetime | None = Query(None, description="Fecha fin (ISO)"),
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista correos con filtros opcionales."""
    skip, limit = pagination

    # Build base query
    base = select(Email)
    count_base = select(func.count(Email.id))

    if category:
        base = base.where(Email.category == category)
        count_base = count_base.where(Email.category == category)
    if status:
        base = base.where(Email.status == status)
        count_base = count_base.where(Email.status == status)
    if date_from:
        base = base.where(Email.received_at >= date_from)
        count_base = count_base.where(Email.received_at >= date_from)
    if date_to:
        base = base.where(Email.received_at <= date_to)
        count_base = count_base.where(Email.received_at <= date_to)

    # Get total count
    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(base.order_by(Email.received_at.desc()).offset(skip).limit(limit))
    emails = result.scalars().all()

    return EmailList(items=emails, total=total, skip=skip, limit=limit)


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(
    email_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de un correo, incluyendo body, extra_data y classification_history."""
    result = await db.execute(
        select(Email)
        .where(Email.id == email_id)
        .options(selectinload(Email.classification_history))
    )
    email = result.scalar_one_or_none()
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )
    return email


@router.patch("/{email_id}/review", response_model=EmailResponse)
async def review_email(
    email_id: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revisión manual de la categoría de un correo.

    Cambia la categoría, crea un registro en classification_history
    con method='manual_review', y actualiza la categoría del contacto
    asociado si es necesario.
    """
    # 1. Normalizar
    new_category = body.category.strip().lower()
    if new_category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Categoría inválida: debe ser una de {', '.join(sorted(VALID_CATEGORIES))}",
        )

    # 2. Cargar email
    result = await db.execute(
        select(Email)
        .where(Email.id == email_id)
        .options(selectinload(Email.classification_history))
    )
    email = result.scalar_one_or_none()
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    # 3. Actualizar category + status
    old_category = email.category
    email.category = new_category
    email.status = "revisado"

    # 4. Crear registro en classification_history
    now = datetime.now(timezone.utc)
    history_entry = ClassificationHistory(
        id=str(uuid.uuid4()),
        email_id=email.id,
        category=new_category,
        confidence=1.0,
        method="manual_review",
        details={"previous_category": old_category, "reviewer": current_user.username},
        reviewed=True,
        reviewed_by=current_user.username,
        reviewed_at=now,
    )
    db.add(history_entry)

    # 5. Actualizar contacto asociado si el email tiene contacto
    contact_result = await db.execute(
        select(Contact).where(Contact.email == email.sender_email)
    )
    contact = contact_result.scalar_one_or_none()
    if contact is not None:
        contact.category = new_category

    await db.commit()
    await db.refresh(email)

    return email
