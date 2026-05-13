"""
Formal tests for the Auth API (Task 5.2).

Covers:
- POST /api/v1/auth/login — success, invalid password, non-existent user
- GET  /api/v1/auth/me — without token, with valid token, with invalid token
"""


class TestLogin:
    """POST /api/v1/auth/login — credential validation."""

    async def test_login_success(self, client):
        """Login with valid credentials returns 200 + JWT token."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password(self, client):
        """Login with wrong password returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_login_nonexistent_user(self, client):
        """Login with non-existent username returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "admin123"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestMe:
    """GET /api/v1/auth/me — authenticated user info."""

    async def test_me_without_token(self, client):
        """GET /me without Authorization header returns 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_me_with_invalid_token(self, client):
        """GET /me with an invalid token returns 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert response.status_code == 401

    async def test_me_with_valid_token(self, client, auth_headers):
        """GET /me with a valid token returns 200 + user data."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert data["active"] is True
