"""Schemas para el dashboard / KPIs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RecentEmail(BaseModel):
    """Correo reciente para el feed del dashboard."""
    id: str
    subject: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: str
    category: Optional[str] = None
    confidence: float = 0.0
    method: str = "unknown"
    summary: Optional[str] = None
    received_at: Optional[datetime] = None
    resolution: Optional[str] = None         # consensus | majority | llm_judge | fallback
    departments: list[str] = []               # Departamentos destino
    urgency: str = "media"                    # alta | media | baja
    action_required: Optional[str] = None     # pago | soporte | consulta | ...
    reviewed: bool = False                     # Indica si ha sido revisado manualmente


class DashboardSummary(BaseModel):
    """Resumen de KPIs para la pantalla de inicio."""
    total_emails: int
    emails_today: int
    contacts_by_category: dict[str, int]
    opportunities_by_stage: dict[str, int]
    recent_emails: list[RecentEmail] = []
    classification_by_method: dict[str, int] = {}


# ── Series Temporales ────────────────────────────────────────────────────────


class TimeSeriesPoint(BaseModel):
    """Un punto en una serie temporal (fecha + valor)."""
    date: str
    value: float


class CategoryTimeSeriesPoint(BaseModel):
    """Un punto en una serie temporal desglosado por categoría."""
    date: str
    category: str
    value: float


class ForecastByCategory(BaseModel):
    """Predicción agregada de una categoría para los próximos 30 días."""
    category: str
    predicted_count: float
    trend: str  # increasing | decreasing | stable


class ForecastDailyPoint(BaseModel):
    """Predicción diaria detallada por categoría."""
    date: str
    category: str
    predicted_count: float


class ForecastData(BaseModel):
    """Datos completos de forecasting para un horizonte específico."""
    days: int  # 30, 60 o 90
    total: float
    by_category: list[ForecastByCategory]
    daily_projections: list[ForecastDailyPoint]
    method: str = "linear_regression"


class TimeSeriesResponse(BaseModel):
    """Respuesta completa de series temporales + predicciones."""
    volume: list[TimeSeriesPoint]
    by_category: list[CategoryTimeSeriesPoint]
    avg_confidence: list[TimeSeriesPoint]
    contacts_cumulative: list[TimeSeriesPoint]
    forecasts: list[ForecastData]
