"""
Router de dashboard / KPIs.

GET /summary: queries agregadas con asyncio.gather() para minimizar latencia.
Incluye: total_emails, emails_today, contacts_by_category, opportunities_by_stage,
         recent_emails (feed), classification_by_method (donut).
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import ClassificationHistory, Contact, Email, Opportunity, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import DashboardSummary, RecentEmail

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


async def _recent_emails(db: AsyncSession) -> list[RecentEmail]:
    """
    Últimos 10 correos clasificados con su método y confianza.
    Para cada email, toma la clasificación más reciente de classification_history.
    """
    result = await db.execute(
        select(Email)
        .options(selectinload(Email.classification_history))
        .order_by(desc(Email.processed_at))
        .limit(10)
    )
    emails = result.scalars().all()

    items = []
    for email in emails:
        # Tomar la clasificación más reciente (última en la lista por created_at)
        ch_list = sorted(
            email.classification_history or [],
            key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        latest = ch_list[0] if ch_list else None
        items.append(
            RecentEmail(
                id=email.id,
                subject=email.subject,
                sender_name=email.sender_name,
                sender_email=email.sender_email,
                category=email.category,
                confidence=latest.confidence if latest else 0.0,
                method=latest.method if latest else "unknown",
                summary=email.summary,
                received_at=email.received_at,
            )
        )
    return items


async def _classification_by_method(db: AsyncSession) -> dict[str, int]:
    """
    Cuenta clasificaciones por método para el donut del dashboard.
    Usa la clasificación más reciente de cada email para evitar sobre-contar.
    """
    from sqlalchemy import distinct

    # Subquery: latest classification created_at per email
    latest_subq = (
        select(
            ClassificationHistory.email_id,
            func.max(ClassificationHistory.created_at).label("max_created"),
        )
        .group_by(ClassificationHistory.email_id)
        .subquery()
    )

    result = await db.execute(
        select(ClassificationHistory.method, func.count(distinct(ClassificationHistory.email_id)))
        .join(
            latest_subq,
            (ClassificationHistory.email_id == latest_subq.c.email_id)
            & (ClassificationHistory.created_at == latest_subq.c.max_created),
        )
        .group_by(ClassificationHistory.method)
    )
    rows = result.all()
    return {row[0]: row[1] for row in rows}


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen de KPIs para el dashboard. Queries paralelas con gather()."""
    total, today, by_category, by_stage, recent, by_method = await asyncio.gather(
        _total_emails(db),
        _emails_today(db),
        _contacts_by_category(db),
        _opportunities_by_stage(db),
        _recent_emails(db),
        _classification_by_method(db),
    )
    return DashboardSummary(
        total_emails=total,
        emails_today=today,
        contacts_by_category=by_category,
        opportunities_by_stage=by_stage,
        recent_emails=recent,
        classification_by_method=by_method,
    )
