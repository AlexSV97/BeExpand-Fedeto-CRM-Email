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


class DashboardSummary(BaseModel):
    """Resumen de KPIs para la pantalla de inicio."""
    total_emails: int
    emails_today: int
    contacts_by_category: dict[str, int]
    opportunities_by_stage: dict[str, int]
    recent_emails: list[RecentEmail] = []
    classification_by_method: dict[str, int] = {}
