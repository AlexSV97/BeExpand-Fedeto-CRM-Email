"""
Shared test fixtures for the formal M4 API REST test suite.

Provides:
- SQLite in-memory engine (per-test isolation)
- async client with get_db() override
- Seeded admin user + auth token
- seed_data fixture for standard test entities
"""

import pytest
from httpx import AsyncClient, ASGITransport
from passlib.hash import bcrypt
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
TestSession = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables before each test; drop after.

    Ensures test isolation — each test starts with a clean schema.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Async test client with SQLite in-memory DB and seeded admin user.

    Overrides get_db() so all API requests use the test database.
    """
    # Seed admin user (needed for login)
    async with TestSession() as session:
        admin = User(
            id="admin-uuid-1",
            username="admin",
            hashed_password=bcrypt.hash("admin123"),
            role="admin",
            active=True,
        )
        session.add(admin)
        await session.commit()

    # Override get_db with proper commit/rollback behaviour
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
    """Login as admin and return Authorization headers.

    Dependencies: client (which seeds admin user and overrides get_db).
    """
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_data():
    """Seed standard test entities: Account, Email, ClassificationHistory, Contact, Opportunity.

    Each entity uses a fixed ID so tests can reference them reliably.
    """
    async with TestSession() as session:
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

        ch = ClassificationHistory(
            id="ch-1",
            email_id="email-1",
            category="cliente",
            confidence=0.95,
            method="rule_engine",
        )
        session.add(ch)

        contact = Contact(
            id="contact-1",
            name="John Doe",
            email="john@test.com",
            category="cliente",
            email_count=3,
        )
        session.add(contact)

        opp = Opportunity(
            id="opp-1",
            contact_id="contact-1",
            title="Test Opportunity",
            stage="nueva",
        )
        session.add(opp)

        await session.commit()
