"""Schemas para buzones IMAP (accounts)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountCreate(BaseModel):
    """Datos para crear un nuevo buzón IMAP."""
    name: str
    email_host: str
    email_port: int = 993
    email_user: str
    email_pass: str
    provider: str = "other"
    active: bool = True


class AccountResponse(BaseModel):
    """Representación pública de un buzón — NO incluye email_pass."""
    id: str
    name: str
    email_host: str
    email_port: int
    email_user: str
    provider: str
    active: bool
    last_polled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
