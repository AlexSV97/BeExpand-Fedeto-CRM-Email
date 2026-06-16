"""Re-export de todos los schemas para imports limpios.

Uso:
    from src.api.schemas import LoginRequest, TokenResponse, ...
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.audit.models import AuditEvent
from src.api.schemas.auth import LoginRequest, TokenResponse, UserResponse
from src.api.schemas.account import AccountCreate, AccountResponse
from src.api.schemas.email import EmailResponse, EmailList, EmailDetailResponse, ClassificationHistoryItem
from src.api.schemas.contact import ContactResponse, ContactUpdate
from src.api.schemas.opportunity import (
    OpportunityCreate,
    OpportunityUpdate,
    OpportunityResponse,
)
from src.api.schemas.classification import ClassificationResponse
from src.api.schemas.dashboard import (
    CategoryTimeSeriesPoint,
    DashboardSummary,
    ForecastByCategory,
    ForecastDailyPoint,
    ForecastData,
    RecentEmail,
    TimeSeriesPoint,
    TimeSeriesResponse,
)


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

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "AccountCreate",
    "AccountResponse",
    "EmailResponse",
    "EmailList",
    "EmailDetailResponse",
    "ClassificationHistoryItem",
    "ContactResponse",
    "ContactUpdate",
    "OpportunityCreate",
    "OpportunityUpdate",
    "OpportunityResponse",
    "ClassificationResponse",
    "DashboardSummary",
    "RecentEmail",
    # Time series
    "TimeSeriesPoint",
    "CategoryTimeSeriesPoint",
    "ForecastByCategory",
    "ForecastDailyPoint",
    "ForecastData",
    "TimeSeriesResponse",
    "OperationalRecordView",
    "OperationalHistoryResponse",
    "AuditTrailResponse",
]
