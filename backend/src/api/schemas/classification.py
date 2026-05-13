"""Schemas para historial de clasificación."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClassificationResponse(BaseModel):
    """Entrada del historial de clasificación de un correo."""
    id: str
    email_id: str
    category: str
    confidence: float
    method: str
    details: Optional[dict] = None
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
