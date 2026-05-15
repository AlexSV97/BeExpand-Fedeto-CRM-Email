"""Schemas para correos electrónicos."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EmailResponse(BaseModel):
    """Correo electrónico procesado."""
    id: str
    account_id: str
    message_id: Optional[str] = None
    subject: Optional[str] = None
    sender_email: str
    sender_name: Optional[str] = None
    recipients: Optional[list] = None
    has_attachments: bool = False
    received_at: Optional[datetime] = None
    category: Optional[str] = None
    relevance: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailList(BaseModel):
    """Lista paginada de correos."""
    items: list[EmailResponse]
    total: int
    skip: int
    limit: int
