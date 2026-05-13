"""
Router de dashboard / KPIs.

GET /summary: queries agregadas con asyncio.gather() para minimizar latencia.
Incluye: total_emails, emails_today, contacts_by_category, opportunities_by_stage.
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Contact, Email, Opportunity, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import DashboardSummary

router = APIRouter(tags=["dashboard"])


async def _total_emails(db: AsyncSession) -> int:
    """Cuenta total de correos."""
    result = await db.scalar(select(func.count(Email.id)))
    return result or 0


async def _emails_today(db: AsyncSession) -> int:
    """Cuenta correos recibidos hoy."""
    today = datetime.now(timezone.utc).date()
    result = await db.scalar(
        select(func.count(Email.id)).where(func.date(Email.received_at) == today)
    )
    return result or 0


async def _contacts_by_category(db: AsyncSession) -> dict[str, int]:
    """Agrupa contactos por categoría."""
    result = await db.execute(
        select(Contact.category, func.count(Contact.id)).group_by(Contact.category)
    )
    rows = result.all()
    return {row.category or "sin_categoria": row[1] for row in rows}


async def _opportunities_by_stage(db: AsyncSession) -> dict[str, int]:
    """Agrupa oportunidades por etapa."""
    result = await db.execute(
        select(Opportunity.stage, func.count(Opportunity.id)).group_by(Opportunity.stage)
    )
    rows = result.all()
    return {row.stage: row[1] for row in rows}


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen de KPIs para el dashboard. Queries paralelas con gather()."""
    total, today, by_category, by_stage = await asyncio.gather(
        _total_emails(db),
        _emails_today(db),
        _contacts_by_category(db),
        _opportunities_by_stage(db),
    )
    return DashboardSummary(
        total_emails=total,
        emails_today=today,
        contacts_by_category=by_category,
        opportunities_by_stage=by_stage,
    )
