"""Re-export de todos los schemas para imports limpios.

Uso:
    from src.api.schemas import LoginRequest, TokenResponse, ...
"""

from src.api.schemas.auth import LoginRequest, TokenResponse, UserResponse
from src.api.schemas.account import AccountCreate, AccountResponse
from src.api.schemas.email import EmailResponse, EmailList
from src.api.schemas.contact import ContactResponse, ContactUpdate
from src.api.schemas.opportunity import (
    OpportunityCreate,
    OpportunityUpdate,
    OpportunityResponse,
)
from src.api.schemas.classification import ClassificationResponse
from src.api.schemas.dashboard import DashboardSummary

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "AccountCreate",
    "AccountResponse",
    "EmailResponse",
    "EmailList",
    "ContactResponse",
    "ContactUpdate",
    "OpportunityCreate",
    "OpportunityUpdate",
    "OpportunityResponse",
    "ClassificationResponse",
    "DashboardSummary",
]
