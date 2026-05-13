"""
Router de cuentas (buzones IMAP).

CRUD completo sobre Account model.
AccountResponse excluye email_pass automáticamente (el schema no declara el campo).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Account, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import AccountCreate, AccountResponse

router = APIRouter(tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista cuentas con filtro opcional por active."""
    stmt = select(Account)
    if active is not None:
        stmt = stmt.where(Account.active == active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=AccountResponse)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea una nueva cuenta de buzón IMAP."""
    account = Account(**body.model_dump())
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene detalle de una cuenta por ID."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza una cuenta existente."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    for key, value in body.model_dump().items():
        setattr(account, key, value)
    await db.flush()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina una cuenta."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    await db.delete(account)
    await db.flush()
