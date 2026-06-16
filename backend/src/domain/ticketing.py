from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActorKind(str, Enum):
    HUMAN = "human"
    IA = "ia"
    SYSTEM = "system"


class TicketState(str, Enum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"
    MERGED = "merged"


class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ExternalRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str
    entity_type: str
    external_id: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def matches(self, system: str, entity_type: str | None = None) -> bool:
        return self.system == system and (entity_type is None or self.entity_type == entity_type)


class Queue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    slug: str | None = None
    description: str | None = None
    is_active: bool = True
    external_refs: list[ExternalRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def external_ref(self, system: str, entity_type: str | None = None) -> ExternalRef | None:
        return next((ref for ref in self.external_refs if ref.matches(system, entity_type)), None)


class SLA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    response_time_minutes: int | None = None
    solution_time_minutes: int | None = None
    calendar_name: str | None = None
    is_active: bool = True
    external_refs: list[ExternalRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str
    author_kind: ActorKind
    author_name: str
    author_email: str | None = None
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    is_visible_to_customer: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    external_refs: list[ExternalRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def external_ref(self, system: str, entity_type: str | None = None) -> ExternalRef | None:
        return next((ref for ref in self.external_refs if ref.matches(system, entity_type)), None)


class ArticleDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_kind: ActorKind = ActorKind.SYSTEM
    author_name: str
    author_email: str | None = None
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    is_visible_to_customer: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    queue: Queue
    state: TicketState = TicketState.NEW
    priority: TicketPriority = TicketPriority.NORMAL
    customer_email: str | None = None
    owner: str | None = None
    assigned_to: str | None = None
    sla: SLA | None = None
    articles: list[ArticleDraft] = Field(default_factory=list)
    external_refs: list[ExternalRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: TicketState | None = None
    priority: TicketPriority | None = None
    owner: str | None = None
    assigned_to: str | None = None
    queue: Queue | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketIngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body_text: str
    sender_name: str
    sender_email: str
    body_html: str | None = None
    recipients: list[str] = Field(default_factory=list)
    message_id: str | None = None
    received_at: datetime | None = None
    queue: Queue | None = None
    priority: TicketPriority = TicketPriority.NORMAL
    state: TicketState = TicketState.NEW
    comment_text: str | None = None
    comment_visible_to_customer: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Ticket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    queue: Queue
    state: TicketState = TicketState.NEW
    priority: TicketPriority = TicketPriority.NORMAL
    customer_email: str | None = None
    owner: str | None = None
    assigned_to: str | None = None
    sla: SLA | None = None
    articles: list[Article] = Field(default_factory=list)
    external_refs: list[ExternalRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def external_ref(self, system: str, entity_type: str | None = None) -> ExternalRef | None:
        return next((ref for ref in self.external_refs if ref.matches(system, entity_type)), None)

    def primary_external_ref(self) -> ExternalRef | None:
        return self.external_refs[0] if self.external_refs else None
