"""
Router de oportunidades de negocio.

CRUD completo sobre Opportunity model.
GET list con filtro stage opcional.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Opportunity, User
from src.db.session import get_db

from src.api.deps import get_current_user, pagination_params
from src.api.schemas import OpportunityCreate, OpportunityResponse

router = APIRouter(tags=["opportunities"])


@router.get("")
async def list_opportunities(
    stage: str | None = Query(None, description="Filtrar por etapa"),
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista oportunidades con filtro opcional por stage."""
    skip, limit = pagination

    base = select(Opportunity)
    count_base = select(func.count(Opportunity.id))

    if stage:
        base = base.where(Opportunity.stage == stage)
        count_base = count_base.where(Opportunity.stage == stage)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Opportunity.created_at.desc()).offset(skip).limit(limit)
    )
    opportunities = result.scalars().all()

    return {
        "items": [OpportunityResponse.model_validate(o).model_dump() for o in opportunities],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", response_model=OpportunityResponse)
async def create_opportunity(
    body: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea una nueva oportunidad."""
    opportunity = Opportunity(**body.model_dump())
    db.add(opportunity)
    await db.flush()
    await db.refresh(opportunity)
    return opportunity


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de una oportunidad por ID."""
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    return opportunity


@router.put("/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: str,
    body: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza una oportunidad (reemplazo completo)."""
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    for key, value in body.model_dump().items():
        setattr(opportunity, key, value)
    await db.flush()
    await db.refresh(opportunity)
    return opportunity


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina una oportunidad."""
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    await db.delete(opportunity)
    await db.flush()
