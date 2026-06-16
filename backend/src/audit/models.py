from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuditActorKind(str, Enum):
    HUMAN = "human"
    IA = "ia"
    SYSTEM = "system"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_kind: AuditActorKind
    actor_name: str
    action: str
    resource_type: str
    resource_id: str
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None

    def is_ai(self) -> bool:
        return self.actor_kind is AuditActorKind.IA

    def is_human(self) -> bool:
        return self.actor_kind is AuditActorKind.HUMAN
