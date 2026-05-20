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


class ClassificationHistoryItem(BaseModel):
    """Entrada del historial de clasificación."""
    id: str
    email_id: str
    category: str
    confidence: float
    method: str
    details: Optional[dict] = None
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmailDetailResponse(BaseModel):
    """Correo completo con body, extra_data e historial de clasificación."""
    id: str
    account_id: str
    message_id: Optional[str] = None
    subject: Optional[str] = None
    body_plain: Optional[str] = None
    body_html: Optional[str] = None
    sender_email: str
    sender_name: Optional[str] = None
    recipients: Optional[list] = None
    has_attachments: bool = False
    attachments: Optional[list] = None
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    category: Optional[str] = None
    relevance: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: datetime
    classification_history: list[ClassificationHistoryItem] = []

    model_config = {"from_attributes": True}


class EmailList(BaseModel):
    """Lista paginada de correos."""
    items: list[EmailResponse]
    total: int
    skip: int
    limit: int
