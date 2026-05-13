"""
Router de correos electrónicos.

GET list con filtros: category, status, date_from/to, skip, limit.
GET /{id} detail que incluye classification_history.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Email, User
from src.db.session import get_db

from src.api.deps import get_current_user, pagination_params
from src.api.schemas import EmailList, EmailResponse

router = APIRouter(tags=["emails"])


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
