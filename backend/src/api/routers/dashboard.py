"""
Router de dashboard / KPIs.

GET /summary: queries agregadas con asyncio.gather() para minimizar latencia.
GET /timeseries: series temporales (volumen, categorías, confianza, contactos) + predicciones.
"""

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.forecasting import forecast_category, trend_direction
from src.db.models import ClassificationHistory, Contact, Email, Opportunity, User
from src.db.session import get_db

from src.api.deps import get_current_user
from src.api.schemas import (
    CategoryTimeSeriesPoint,
    DashboardSummary,
    ForecastByCategory,
    ForecastDailyPoint,
    ForecastData,
    RecentEmail,
    TimeSeriesPoint,
    TimeSeriesResponse,
)

HORIZONS = [30, 60, 90]

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
        # Extraer datos del orquestador desde extra_data (JSON)
        extra = email.extra_data or {}
        routing_data = extra.get("routing", {})
        analyzer_data = extra.get("analyzer", {})

        # ¿Tiene alguna revisión manual?
        reviewed = any(
            ch.method == "manual_review" and ch.reviewed
            for ch in (email.classification_history or [])
        )

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
                resolution=extra.get("resolution_method"),
                departments=routing_data.get("departments", []),
                urgency=analyzer_data.get("urgency", "media"),
                action_required=analyzer_data.get("action_required"),
                reviewed=reviewed,
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


# ── Helper: date_trunc cross-dialect ──


def _date_col(column: Any) -> Any:
    """Trunca un timestamp a fecha (día). Funciona en SQLite y PostgreSQL.

    SQLite:  date(col)        → 'YYYY-MM-DD' (texto)
    PostgreSQL: date(col)     → date
    """
    return func.date(column)


# ── Queries de series temporales ──


async def _email_volume(
    db: AsyncSession, start: date, end: date,
) -> list[TimeSeriesPoint]:
    """Volumen de correos agrupado por día."""
    dc = _date_col(Email.received_at)
    result = await db.execute(
        select(dc.label("dt"), func.count(Email.id).label("cnt"))
        .where(Email.received_at >= start)
        .where(Email.received_at < end + timedelta(days=1))
        .group_by(dc)
        .order_by(dc)
    )
    return [TimeSeriesPoint(date=str(r.dt), value=float(r.cnt)) for r in result.all()]


async def _email_by_category(
    db: AsyncSession, start: date, end: date,
) -> list[CategoryTimeSeriesPoint]:
    """Correos por día y categoría (para stacked area)."""
    dc = _date_col(Email.received_at)
    result = await db.execute(
        select(
            dc.label("dt"),
            Email.category,
            func.count(Email.id).label("cnt"),
        )
        .where(Email.received_at >= start)
        .where(Email.received_at < end + timedelta(days=1))
        .group_by(dc, Email.category)
        .order_by(dc, Email.category)
    )
    return [
        CategoryTimeSeriesPoint(
            date=str(r.dt),
            category=r.category or "sin_categoria",
            value=float(r.cnt),
        )
        for r in result.all()
    ]


async def _avg_confidence(
    db: AsyncSession, start: date, end: date,
) -> list[TimeSeriesPoint]:
    """Confianza media por día (desde classification_history)."""
    dc = _date_col(ClassificationHistory.created_at)
    result = await db.execute(
        select(dc.label("dt"), func.avg(ClassificationHistory.confidence).label("avg_conf"))
        .where(ClassificationHistory.created_at >= start)
        .where(ClassificationHistory.created_at < end + timedelta(days=1))
        .group_by(dc)
        .order_by(dc)
    )
    return [
        TimeSeriesPoint(date=str(r.dt), value=round(float(r.avg_conf), 4))
        for r in result.all()
    ]


async def _contacts_cumulative(
    db: AsyncSession, start: date, end: date,
) -> list[TimeSeriesPoint]:
    """Contactos nuevos acumulados por día."""
    dc = _date_col(Contact.created_at)
    result = await db.execute(
        select(dc.label("dt"), func.count(Contact.id).label("cnt"))
        .where(Contact.created_at >= start)
        .where(Contact.created_at < end + timedelta(days=1))
        .group_by(dc)
        .order_by(dc)
    )
    rows = result.all()

    cumulative = 0
    points: list[TimeSeriesPoint] = []
    for r in rows:
        cumulative += int(r.cnt)
        points.append(TimeSeriesPoint(date=str(r.dt), value=float(cumulative)))
    return points


def _pad_dates(daily_counts: list[tuple[date, int]]) -> list[tuple[date, int]]:
    """Rellena días faltantes entre el primer y último dato con interpolación lineal.

    Útil cuando hay pocos datos históricos: evita que el modelo caiga a media
    simple al tener < 3 puntos. Cuando los gaps se cierren con datos reales
    esta función deja de tener efecto.
    """
    if len(daily_counts) < 2:
        return daily_counts
    sorted_vals = sorted(daily_counts, key=lambda x: x[0])
    result: list[tuple[date, int]] = []
    for i in range(len(sorted_vals) - 1):
        curr_date, curr_val = sorted_vals[i]
        next_date, next_val = sorted_vals[i + 1]
        result.append((curr_date, curr_val))
        gap = (next_date - curr_date).days
        if gap > 1:
            for j in range(1, gap):
                interp_date = curr_date + timedelta(days=j)
                interp_val = curr_val + (next_val - curr_val) * j / gap
                result.append((interp_date, round(interp_val)))
    result.append(sorted_vals[-1])
    return result


async def _compute_forecast(
    db: AsyncSession, start: date, end: date,
) -> list[ForecastData]:
    """Calcula predicciones a 30, 60 y 90 días usando regresión lineal.

    Toma los últimos 90 días de datos históricos para entrenar
    el modelo por categoría. Devuelve un ForecastData por horizonte.
    """
    today = datetime.now(timezone.utc).date()
    forecast_start = today - timedelta(days=90)
    if forecast_start < start:
        forecast_start = start

    dc = _date_col(Email.received_at)
    result = await db.execute(
        select(
            dc.label("dt"),
            Email.category,
            func.count(Email.id).label("cnt"),
        )
        .where(Email.received_at >= forecast_start)
        .where(Email.received_at < today + timedelta(days=1))
        .group_by(dc, Email.category)
        .order_by(dc, Email.category)
    )
    rows = result.all()

    # Agrupar por categoría
    daily_by_cat: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for r in rows:
        cat = r.category or "sin_categoria"
        row_date = (
            r.dt if isinstance(r.dt, date)
            else date.fromisoformat(str(r.dt))
        )
        daily_by_cat[cat].append((row_date, int(r.cnt)))

    forecast_categories = [
        (cat, daily_by_cat.get(cat, []))
        for cat in ["cliente", "lead", "proveedor", "nulo"]
    ]

    forecasts: list[ForecastData] = []
    for days in HORIZONS:
        total = 0.0
        categories_summary: list[ForecastByCategory] = []
        daily_projections: list[ForecastDailyPoint] = []

        for cat, counts in forecast_categories:
            counts_sorted = sorted(counts, key=lambda x: x[0])
            counts_padded = _pad_dates(counts_sorted)
            predictions = forecast_category(counts_padded, days_ahead=days)
            direction = trend_direction(counts_sorted) if counts_sorted else "stable"

            cat_total = sum(p for _, p in predictions)
            total += cat_total

            categories_summary.append(ForecastByCategory(
                category=cat,
                predicted_count=round(cat_total, 1),
                trend=direction,
            ))

            for pred_date, pred_val in predictions:
                daily_projections.append(ForecastDailyPoint(
                    date=str(pred_date),
                    category=cat,
                    predicted_count=pred_val,
                ))

        forecasts.append(ForecastData(
            days=days,
            total=round(total, 1),
            by_category=categories_summary,
            daily_projections=daily_projections,
            method="linear_regression",
        ))

    return forecasts


# ── Endpoint principal ──


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    period: str = Query("30d", pattern=r"^(7d|30d|90d|all)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Series temporales (volumen, categorías, confianza, contactos) + predicción 30 días.

    - period: 7d | 30d | 90d | all
    - from / to: filtros opcionales de fecha (ISO, YYYY-MM-DD)
    """
    today = datetime.now(timezone.utc).date()

    # Calcular rango por defecto según period
    period_map = {"7d": 7, "30d": 30, "90d": 90}
    if period == "all":
        start = date(2000, 1, 1)
    else:
        start = today - timedelta(days=period_map[period])

    if from_date:
        start = datetime.fromisoformat(from_date).date()
    if to_date:
        end = datetime.fromisoformat(to_date).date()
    else:
        end = today

    volume, by_cat, avg_conf, contacts, forecasts = await asyncio.gather(
        _email_volume(db, start, end),
        _email_by_category(db, start, end),
        _avg_confidence(db, start, end),
        _contacts_cumulative(db, start, end),
        _compute_forecast(db, start, end),
    )

    return TimeSeriesResponse(
        volume=volume,
        by_category=by_cat,
        avg_confidence=avg_conf,
        contacts_cumulative=contacts,
        forecasts=forecasts,
    )
