"""
Router de correos electrónicos.

GET list con filtros: category, status, date_from/to, skip, limit.
GET /{id} detail que incluye classification_history.
PATCH /{id}/review — revisión manual de categoría por un usuario.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import ClassificationHistory, Contact, Email, User
from src.db.session import get_db

from src.api.deps import get_current_user, pagination_params
from src.api.schemas import EmailList, EmailResponse
from src.email_processor import sync_emails

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


@router.get("/{email_id}")
async def get_email(
    email_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de un correo, incluyendo classification_history."""
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

    # Build base response and augment with classification_history
    email_data = EmailResponse.model_validate(email).model_dump()
    email_data["classification_history"] = [
        {
            "id": ch.id,
            "email_id": ch.email_id,
            "category": ch.category,
            "confidence": ch.confidence,
            "method": ch.method,
            "details": ch.details,
            "reviewed": ch.reviewed,
            "reviewed_by": ch.reviewed_by,
            "reviewed_at": ch.reviewed_at,
            "created_at": ch.created_at,
        }
        for ch in email.classification_history
    ]
    return email_data


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
