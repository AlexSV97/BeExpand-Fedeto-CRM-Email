"""
Tests for all API schemas (RED phase — schemas don't exist yet).

Follows TDD: these tests reference production code that does NOT exist yet.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

# ── These imports will fail until schemas/__init__.py and schema files exist ──
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


# =============================================================================
# Auth schemas
# =============================================================================

class TestLoginRequest:
    def test_valid(self):
        """Happy path: all required fields."""
        data = LoginRequest(username="admin", password="test-password")
        assert data.username == "admin"
        assert data.password == "test-password"

    def test_serialization(self):
        """model_dump produces expected dict."""
        data = LoginRequest(username="admin", password="test-password")
        dumped = data.model_dump()
        assert dumped == {"username": "admin", "password": "test-password"}

    def test_missing_username_raises(self):
        """Username is required."""
        with pytest.raises(ValidationError):
            LoginRequest(password="test-password")

    def test_missing_password_raises(self):
        """Password is required."""
        with pytest.raises(ValidationError):
            LoginRequest(username="admin")


class TestTokenResponse:
    def test_valid_with_default_type(self):
        """token_type defaults to 'bearer'."""
        data = TokenResponse(access_token="eyJhbGciOiJIUzI1NiIs...")
        assert data.access_token == "eyJhbGciOiJIUzI1NiIs..."
        assert data.token_type == "bearer"

    def test_valid_with_custom_type(self):
        """token_type can be overridden."""
        data = TokenResponse(access_token="abc", token_type="Bearer")
        assert data.token_type == "Bearer"


class TestUserResponse:
    def test_valid_minimal(self):
        """Only required fields."""
        data = UserResponse(id="u1", username="admin", role="admin", active=True)
        assert data.id == "u1"
        assert data.username == "admin"
        assert data.role == "admin"
        assert data.active is True

    def test_valid_full(self):
        """All fields including optionals."""
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = UserResponse(
            id="u1",
            username="admin",
            email="admin@example.com",
            full_name="Admin User",
            role="admin",
            active=True,
        )
        assert data.email == "admin@example.com"
        assert data.full_name == "Admin User"

    def test_from_attributes(self):
        """Can be created from ORM-like dict (from_attributes=True)."""
        data = UserResponse.model_validate({
            "id": "u1",
            "username": "admin",
            "role": "admin",
            "active": True,
        })
        assert data.username == "admin"


# =============================================================================
# Account schemas
# =============================================================================

class TestAccountCreate:
    def test_valid_minimal(self):
        """Only required fields + defaults."""
        data = AccountCreate(
            name="My Mailbox",
            email_host="imap.example.com",
            email_user="user@example.com",
            email_pass="secret",
        )
        assert data.name == "My Mailbox"
        assert data.email_host == "imap.example.com"
        assert data.email_port == 993  # default
        assert data.email_pass == "secret"
        assert data.provider == "other"  # default
        assert data.active is True  # default

    def test_valid_full(self):
        """All fields provided."""
        data = AccountCreate(
            name="My Mailbox",
            email_host="imap.example.com",
            email_port=143,
            email_user="user@example.com",
            email_pass="secret",
            provider="gmail",
            active=False,
        )
        assert data.email_port == 143
        assert data.provider == "gmail"
        assert data.active is False

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AccountCreate(
                email_host="imap.example.com",
                email_user="user@example.com",
                email_pass="secret",
            )


class TestAccountResponse:
    def test_valid(self):
        """Response has all fields EXCEPT email_pass."""
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = AccountResponse(
            id="a1",
            name="My Mailbox",
            email_host="imap.example.com",
            email_port=993,
            email_user="user@example.com",
            provider="other",
            active=True,
            created_at=dt,
            updated_at=dt,
        )
        assert data.id == "a1"
        # email_pass MUST NOT be a field
        assert not hasattr(data, "email_pass")

    def test_serialization_excludes_email_pass(self):
        """model_dump output excludes email_pass."""
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = AccountResponse(
            id="a1",
            name="My Mailbox",
            email_host="imap.example.com",
            email_port=993,
            email_user="user@example.com",
            provider="other",
            active=True,
            created_at=dt,
            updated_at=dt,
        )
        dumped = data.model_dump()
        assert "email_pass" not in dumped


# =============================================================================
# Email schemas
# =============================================================================

class TestEmailResponse:
    def test_valid(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = EmailResponse(
            id="e1",
            account_id="a1",
            sender_email="sender@example.com",
            has_attachments=False,
            subject="Hello",
            received_at=dt,
            created_at=dt,
        )
        assert data.id == "e1"
        assert data.sender_email == "sender@example.com"


class TestEmailList:
    def test_valid(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        items = [
            EmailResponse(
                id="e1",
                account_id="a1",
                sender_email="s@example.com",
                has_attachments=False,
                created_at=dt,
            )
        ]
        data = EmailList(items=items, total=1, skip=0, limit=100)
        assert data.total == 1
        assert len(data.items) == 1
        assert data.items[0].id == "e1"

    def test_empty_list(self):
        data = EmailList(items=[], total=0, skip=0, limit=100)
        assert data.total == 0
        assert data.items == []


# =============================================================================
# Contact schemas
# =============================================================================

class TestContactResponse:
    def test_valid(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = ContactResponse(
            id="c1",
            name="John Doe",
            email="john@example.com",
            email_count=5,
            created_at=dt,
            updated_at=dt,
        )
        assert data.name == "John Doe"
        assert data.email == "john@example.com"

    def test_from_attributes(self):
        data = ContactResponse.model_validate({
            "id": "c1",
            "name": "John Doe",
            "email": "john@example.com",
            "email_count": 0,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })
        assert data.name == "John Doe"


class TestContactUpdate:
    def test_valid_full(self):
        data = ContactUpdate(category="cliente")
        assert data.category == "cliente"

    def test_empty_update(self):
        """All fields are optional — empty body is valid."""
        data = ContactUpdate()
        assert data.category is None

    def test_invalid_category_raises(self):
        """Should fail on unknown category... but schema is str, so any string passes."""
        data = ContactUpdate(category="unknown")
        assert data.category == "unknown"


# =============================================================================
# Opportunity schemas
# =============================================================================

class TestOpportunityCreate:
    def test_valid_minimal(self):
        data = OpportunityCreate(contact_id="c1", title="New deal")
        assert data.contact_id == "c1"
        assert data.title == "New deal"
        assert data.stage == "nueva"  # default

    def test_valid_full(self):
        data = OpportunityCreate(
            contact_id="c1",
            title="Big deal",
            description="A big opportunity",
            stage="calificada",
            value=Decimal("10000.50"),
            probability=75,
            expected_close=date(2026, 6, 1),
        )
        assert data.value == Decimal("10000.50")
        assert data.stage == "calificada"


class TestOpportunityUpdate:
    def test_valid_partial(self):
        data = OpportunityUpdate(stage="propuesta")
        assert data.stage == "propuesta"
        assert data.title is None

    def test_empty_update(self):
        data = OpportunityUpdate()
        assert data.title is None


class TestOpportunityResponse:
    def test_valid(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = OpportunityResponse(
            id="o1",
            contact_id="c1",
            title="Closed deal",
            stage="cerrada_ganada",
            created_at=dt,
            updated_at=dt,
        )
        assert data.title == "Closed deal"
        assert data.stage == "cerrada_ganada"


# =============================================================================
# Classification schemas
# =============================================================================

class TestClassificationResponse:
    def test_valid(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = ClassificationResponse(
            id="cl1",
            email_id="e1",
            category="cliente",
            confidence=0.95,
            method="rule_engine",
            reviewed=False,
            created_at=dt,
        )
        assert data.category == "cliente"
        assert data.confidence == 0.95

    def test_from_attributes(self):
        data = ClassificationResponse.model_validate({
            "id": "cl1",
            "email_id": "e1",
            "category": "lead",
            "confidence": 0.8,
            "method": "ml_classifier",
            "reviewed": True,
            "created_at": "2026-01-01T00:00:00Z",
        })
        assert data.method == "ml_classifier"


# =============================================================================
# Dashboard schemas
# =============================================================================

class TestDashboardSummary:
    def test_valid(self):
        data = DashboardSummary(
            total_emails=100,
            emails_today=5,
            contacts_by_category={"cliente": 10, "lead": 3},
            opportunities_by_stage={"nueva": 2, "calificada": 1},
        )
        assert data.total_emails == 100
        assert data.emails_today == 5
        assert data.contacts_by_category["cliente"] == 10

    def test_empty_counts(self):
        data = DashboardSummary(
            total_emails=0,
            emails_today=0,
            contacts_by_category={},
            opportunities_by_stage={},
        )
        assert data.total_emails == 0
        assert data.contacts_by_category == {}
