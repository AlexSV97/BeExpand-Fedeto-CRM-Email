"""
Integration tests for the auth endpoint (RED phase — auth router + deps don't exist yet).

Tests login and /me endpoints through TestClient with in-memory SQLite.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from src.utils.passwords import hash_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.api.main import app
from src.db.models import User
from src.db.session import Base, get_db

TEST_ADMIN_PASSWORD = "test-admin-password"

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables + seed admin user before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as session:
        admin = User(
            id="admin-uuid-1",
            username="admin",
            hashed_password=hash_password(TEST_ADMIN_PASSWORD),
            role="admin",
            active=True,
        )
        session.add(admin)
        await session.commit()

    # Override get_db to use our test DB
    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

    # Clean up DB
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_login_success(client):
    """POST /api/v1/auth/login with valid credentials returns 200 + token."""
    response = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD,
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    """POST /api/v1/auth/login with wrong password returns 401."""
    response = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_login_invalid_username(client):
    """POST /api/v1/auth/login with non-existent user returns 401."""
    response = await client.post("/api/v1/auth/login", json={
        "username": "nonexistent",
        "password": TEST_ADMIN_PASSWORD,
    })
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_me_without_token(client):
    """GET /api/v1/auth/me without Authorization header returns 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token(client):
    """GET /api/v1/auth/me with invalid token returns 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalidtoken123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client):
    """GET /api/v1/auth/me with valid token returns user info."""
    # First login to get token
    login_resp = await client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD,
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Use token to access /me
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["active"] is True
