from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.audit.models import AuditEvent


class OperationalRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    record_kind: str
    resource_id: str | None = None
    actor_kind: str | None = None
    actor_name: str | None = None
    status: str | None = None
    title: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OperationalHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OperationalRecordView]
    total: int


class AuditTrailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEvent]
    total: int