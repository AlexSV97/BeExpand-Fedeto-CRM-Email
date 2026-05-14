"""Schemas para oportunidades de negocio."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class OpportunityCreate(BaseModel):
    """Datos para crear una nueva oportunidad."""
    email_id: Optional[str] = None
    contact_id: str
    title: str
    description: Optional[str] = None
    stage: str = "nueva"
    value: Optional[Decimal] = None
    probability: Optional[int] = None
    expected_close: Optional[date] = None
    notes: Optional[str] = None


class OpportunityUpdate(BaseModel):
    """Datos actualizables de una oportunidad."""
    title: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    value: Optional[Decimal] = None
    probability: Optional[int] = None
    expected_close: Optional[date] = None
    notes: Optional[str] = None


class OpportunityResponse(BaseModel):
    """Oportunidad de negocio (respuesta completa)."""
    id: str
    email_id: Optional[str] = None
    contact_id: str
    title: str
    description: Optional[str] = None
    stage: str
    value: Optional[Decimal] = None
    probability: Optional[int] = None
    expected_close: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
