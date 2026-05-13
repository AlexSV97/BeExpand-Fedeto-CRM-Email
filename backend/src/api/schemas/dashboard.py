"""Schemas para el dashboard / KPIs."""

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Resumen de KPIs para la pantalla de inicio."""
    total_emails: int
    emails_today: int
    contacts_by_category: dict[str, int]
    opportunities_by_stage: dict[str, int]
