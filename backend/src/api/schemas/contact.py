"""Schemas para contactos."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContactResponse(BaseModel):
    """Contacto sincronizado con CRM."""
    id: str
    crm_id: Optional[str] = None
    name: str
    email: str
    company: Optional[str] = None
    position: Optional[str] = None
    category: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    email_count: int = 0
    first_email_at: Optional[datetime] = None
    last_email_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactUpdate(BaseModel):
    """Datos actualizables de un contacto (PATCH)."""
    category: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
