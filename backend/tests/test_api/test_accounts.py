"""
Formal tests for the Accounts API (Task 5.3).

Covers full CRUD cycle plus:
- email_pass exclusion from response
- active filter
"""


class TestAccountsCRUD:
    """Full CRUD cycle for /api/v1/accounts."""

    async def test_create_account(self, client, auth_headers):
        """POST /api/v1/accounts creates an account and excludes email_pass."""
        response = await client.post(
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
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Mailbox"
        assert data["email_host"] == "imap.example.com"
        assert data["email_user"] == "user@example.com"
        assert "email_pass" not in data, (
            "email_pass MUST be excluded from AccountResponse"
        )

    async def test_list_accounts(self, client, auth_headers, seed_data):
        """GET /api/v1/accounts returns list of accounts."""
        response = await client.get("/api/v1/accounts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = [acct["id"] for acct in data]
        assert "acct-1" in ids

    async def test_get_account_by_id(self, client, auth_headers, seed_data):
        """GET /api/v1/accounts/{id} returns account detail."""
        response = await client.get(
            "/api/v1/accounts/acct-1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "acct-1"
        assert data["name"] == "Test Mailbox"
        assert "email_pass" not in data

    async def test_update_account(self, client, auth_headers):
        """PUT /api/v1/accounts/{id} updates an existing account."""
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

    async def test_delete_account(self, client, auth_headers):
        """DELETE /api/v1/accounts/{id} removes the account."""
        # Create
        create_resp = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "ToDelete",
                "email_host": "imap.del.com",
                "email_user": "del@test.com",
                "email_pass": "del123",
            },
        )
        acct_id = create_resp.json()["id"]

        # Delete
        delete_resp = await client.delete(
            f"/api/v1/accounts/{acct_id}", headers=auth_headers
        )
        assert delete_resp.status_code == 204

        # Verify deleted
        get_resp = await client.get(
            f"/api/v1/accounts/{acct_id}", headers=auth_headers
        )
        assert get_resp.status_code == 404

    async def test_list_with_active_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/accounts?active=true returns active accounts only."""
        response = await client.get(
            "/api/v1/accounts?active=true", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Seed data has a single active account
        assert any(acct["id"] == "acct-1" for acct in data)
        for acct in data:
            assert acct["active"] is True
