"""
TDD safety-net tests for PR 2 — Core Routers (RED phase).

These tests verify that each router endpoint exists and returns correct
responses. They are kept simple/small — formal per-domain tests come in PR 3.

IMPORTANT: These tests reference production code (routers) that does NOT exist
yet. They WILL fail until the routers are implemented (RED → GREEN).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from src.utils.passwords import hash_password
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.api.main import app
from src.db.models import (
    Account,
    ClassificationHistory,
    Contact,
    Email,
    Opportunity,
    User,
)
from src.db.session import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables before each test; drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Async test client with in-memory DB override + seeded admin user."""

    # Seed admin user (needed for login)
    async with TestSession() as session:
        admin = User(
            id="admin-uuid-1",
            username="admin",
            hashed_password=hash_password("admin123"),
            role="admin",
            active=True,
        )
        session.add(admin)
        await session.commit()

    # Override get_db with commit (mimics real get_db)
    async def _override_get_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client):
    """Login as admin and return Authorization headers for protected endpoints."""
    response = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_data():
    """Seed various test entities so router tests have non-empty data."""

    async with TestSession() as session:
        # Account
        account = Account(
            id="acct-1",
            name="Test Mailbox",
            email_host="imap.test.com",
            email_port=993,
            email_user="test@test.com",
            email_pass="supersecret",
            provider="other",
            active=True,
        )
        session.add(account)

        # Email
        email = Email(
            id="email-1",
            account_id="acct-1",
            sender_email="sender@test.com",
            sender_name="Sender",
            subject="Test Email",
            category="cliente",
            status="pendiente",
        )
        session.add(email)

        # ClassificationHistory
        ch = ClassificationHistory(
            id="ch-1",
            email_id="email-1",
            category="cliente",
            confidence=0.95,
            method="rule_engine",
        )
        session.add(ch)

        # Contact
        contact = Contact(
            id="contact-1",
            name="John Doe",
            email="john@test.com",
            category="cliente",
            email_count=3,
        )
        session.add(contact)

        # Opportunity
        opp = Opportunity(
            id="opp-1",
            contact_id="contact-1",
            title="Test Opportunity",
            stage="nueva",
        )
        session.add(opp)

        await session.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.1 — Accounts CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestAccountsRouter:
    """RED: accounts router does not exist yet — these tests WILL fail."""

    async def test_list_empty(self, client, auth_headers):
        """GET /api/v1/accounts returns empty list when no accounts exist."""
        response = await client.get("/api/v1/accounts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_create_and_get(self, client, auth_headers):
        """POST + GET /{id} create and retrieve an Account, email_pass excluded."""
        # Create
        create_resp = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "My Mailbox",
                "email_host": "imap.example.com",
                "email_port": 993,
                "email_user": "user@example.com",
                "email_pass": "secret123",
                "provider": "other",
                "active": True,
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()
        assert created["name"] == "My Mailbox"
        assert "email_pass" not in created, "email_pass MUST be excluded from response"

        # Get by id
        get_resp = await client.get(
            f"/api/v1/accounts/{created['id']}", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "My Mailbox"

    async def test_update_and_delete(self, client, auth_headers):
        """PUT + DELETE full CRUD cycle."""
        # Create
        create_resp = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "Temp",
                "email_host": "imap.temp.com",
                "email_user": "temp@test.com",
                "email_pass": "temp123",
            },
        )
        acct_id = create_resp.json()["id"]

        # Update
        update_resp = await client.put(
            f"/api/v1/accounts/{acct_id}",
            headers=auth_headers,
            json={
                "name": "Updated",
                "email_host": "imap.updated.com",
                "email_user": "updated@test.com",
                "email_pass": "newpass",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated"

        # Delete
        delete_resp = await client.delete(
            f"/api/v1/accounts/{acct_id}", headers=auth_headers
        )
        assert delete_resp.status_code == 204

    async def test_list_with_active_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/accounts?active=true filters correctly."""
        response = await client.get(
            "/api/v1/accounts?active=true", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(acct["id"] == "acct-1" for acct in data)


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.2 — Emails list + detail
# ═══════════════════════════════════════════════════════════════════════════

class TestEmailsRouter:
    """RED: emails router does not exist yet — these tests WILL fail."""

    async def test_list_with_filters(self, client, auth_headers, seed_data):
        """GET /api/v1/emails accepts category, status, skip, limit filters."""
        response = await client.get(
            "/api/v1/emails?category=cliente&skip=0&limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # EmailList format {items, total, skip, limit}
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["items"][0]["category"] == "cliente"

    async def test_detail_includes_classification_history(self, client, auth_headers, seed_data):
        """GET /api/v1/emails/{id} includes classification_history."""
        response = await client.get("/api/v1/emails/email-1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "email-1"
        assert "classification_history" in data


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.3 — Contacts list, detail, patch
# ═══════════════════════════════════════════════════════════════════════════

class TestContactsRouter:
    """RED: contacts router does not exist yet — these tests WILL fail."""

    async def test_list_with_search(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts with search filter returns matching contacts."""
        response = await client.get(
            "/api/v1/contacts?search=John&skip=0&limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1
        assert data["items"][0]["name"] == "John Doe"

    async def test_detail_and_patch(self, client, auth_headers, seed_data):
        """GET detail + PATCH update category."""
        # Detail
        get_resp = await client.get(
            "/api/v1/contacts/contact-1", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "John Doe"

        # Patch
        patch_resp = await client.patch(
            "/api/v1/contacts/contact-1",
            headers=auth_headers,
            json={"category": "lead"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["category"] == "lead"


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.4 — Opportunities CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestOpportunitiesRouter:
    """RED: opportunities router does not exist yet — these tests WILL fail."""

    async def test_crud_cycle(self, client, auth_headers, seed_data):
        """Full CRUD cycle: create, get, update, delete, list with filter."""
        # Create
        create_resp = await client.post(
            "/api/v1/opportunities",
            headers=auth_headers,
            json={
                "contact_id": "contact-1",
                "title": "New Deal",
                "stage": "nueva",
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()
        assert created["title"] == "New Deal"
        opp_id = created["id"]

        # Get detail
        get_resp = await client.get(
            f"/api/v1/opportunities/{opp_id}", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "New Deal"

        # Update
        update_resp = await client.put(
            f"/api/v1/opportunities/{opp_id}",
            headers=auth_headers,
            json={
                "contact_id": "contact-1",
                "title": "Updated Deal",
                "stage": "calificada",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["stage"] == "calificada"

        # Delete
        delete_resp = await client.delete(
            f"/api/v1/opportunities/{opp_id}", headers=auth_headers
        )
        assert delete_resp.status_code == 204

        # List with stage filter
        list_resp = await client.get(
            "/api/v1/opportunities?stage=nueva", headers=auth_headers
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.5 — Classification list + detail
# ═══════════════════════════════════════════════════════════════════════════

class TestClassificationRouter:
    """RED: classification router does not exist yet — these tests WILL fail."""

    async def test_list_by_email_id(self, client, auth_headers, seed_data):
        """GET /api/v1/classification-history?email_id=... returns matching records."""
        response = await client.get(
            "/api/v1/classification-history?email_id=email-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1
        assert data["items"][0]["category"] == "cliente"

    async def test_detail(self, client, auth_headers, seed_data):
        """GET /api/v1/classification-history/{id} returns single record."""
        response = await client.get(
            "/api/v1/classification-history/ch-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == "ch-1"


# ═══════════════════════════════════════════════════════════════════════════
# Task 3.6 — Dashboard /summary
# ═══════════════════════════════════════════════════════════════════════════

class TestDashboardRouter:
    """RED: dashboard router does not exist yet — these tests WILL fail."""

    async def test_summary_with_data(self, client, auth_headers, seed_data):
        """GET /api/v1/dashboard/summary returns KPIs with seed data."""
        response = await client.get(
            "/api/v1/dashboard/summary", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_emails" in data
        assert "emails_today" in data
        assert "contacts_by_category" in data
        assert "opportunities_by_stage" in data
        # With seed data: at least 1 email, 1 contact, 1 opportunity
        assert data["total_emails"] >= 1
        assert data["contacts_by_category"].get("cliente", 0) >= 1
        assert data["opportunities_by_stage"].get("nueva", 0) >= 1

    async def test_summary_empty_db(self, client, auth_headers):
        """GET /api/v1/dashboard/summary returns zeros with no data."""
        response = await client.get(
            "/api/v1/dashboard/summary", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 0
        assert data["emails_today"] == 0
        assert data["contacts_by_category"] == {}
        assert data["opportunities_by_stage"] == {}
