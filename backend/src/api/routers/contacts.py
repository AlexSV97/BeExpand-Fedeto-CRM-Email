"""
Router de contactos.

GET list con filtros: category, search (name/email), skip, limit.
GET /{id} detail.
PATCH /{id} update category.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Contact, User
from src.db.session import get_db

from src.api.deps import get_current_user, pagination_params
from src.api.schemas import ContactResponse, ContactUpdate

router = APIRouter(tags=["contacts"])


@router.get("")
async def list_contacts(
    category: str | None = Query(None, description="Filtrar por categoría"),
    search: str | None = Query(None, description="Buscar por nombre o email"),
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista contactos con filtros opcionales."""
    skip, limit = pagination

    base = select(Contact)
    count_base = select(func.count(Contact.id))

    if category:
        base = base.where(Contact.category == category)
        count_base = count_base.where(Contact.category == category)
    if search:
        search_filter = or_(
            Contact.name.ilike(f"%{search}%"),
            Contact.email.ilike(f"%{search}%"),
        )
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Contact.name).offset(skip).limit(limit)
    )
    contacts = result.scalars().all()

    return {
        "items": [ContactResponse.model_validate(c).model_dump() for c in contacts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de un contacto por ID."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    return contact


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    body: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza parcialmente un contacto (categoría, empresa, etc.)."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    await db.flush()
    await db.refresh(contact)
    return contact
