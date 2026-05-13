"""
Router de historial de clasificación.

GET list con filtro email_id.
GET /{id} detail.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ClassificationHistory, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import ClassificationResponse

router = APIRouter(tags=["classification"])


@router.get("")
async def list_classifications(
    email_id: str | None = Query(None, description="Filtrar por email"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista historial de clasificaciones con filtro opcional por email_id."""
    base = select(ClassificationHistory)
    count_base = select(func.count(ClassificationHistory.id))

    if email_id:
        base = base.where(ClassificationHistory.email_id == email_id)
        count_base = count_base.where(ClassificationHistory.email_id == email_id)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(ClassificationHistory.created_at.desc())
    )
    items = result.scalars().all()

    return {
        "items": [ClassificationResponse.model_validate(c).model_dump() for c in items],
        "total": total,
    }


@router.get("/{classification_id}", response_model=ClassificationResponse)
async def get_classification(
    classification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de una clasificación por ID."""
    result = await db.execute(
        select(ClassificationHistory).where(
            ClassificationHistory.id == classification_id
        )
    )
    classification = result.scalar_one_or_none()
    if classification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification not found",
        )
    return classification
