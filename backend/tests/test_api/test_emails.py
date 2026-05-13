"""
Formal tests for the Emails API (Task 5.4).

Covers:
- GET list with pagination
- GET list with category / status / date filters
- GET detail includes classification_history
"""


class TestEmailsList:
    """GET /api/v1/emails — list with filters."""

    async def test_list_paginated(self, client, auth_headers, seed_data):
        """GET /api/v1/emails returns paginated EmailList."""
        response = await client.get(
            "/api/v1/emails?skip=0&limit=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert data["total"] >= 1
        assert data["skip"] == 0
        assert data["limit"] == 10
        assert data["items"][0]["id"] == "email-1"

    async def test_list_with_category_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/emails?category=cliente filters by category."""
        response = await client.get(
            "/api/v1/emails?category=cliente", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["category"] == "cliente"

    async def test_list_with_status_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/emails?status=pendiente filters by status."""
        response = await client.get(
            "/api/v1/emails?status=pendiente", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "pendiente"

    async def test_list_empty_result(self, client, auth_headers):
        """GET /api/v1/emails with no data returns empty list."""
        response = await client.get(
            "/api/v1/emails?skip=0&limit=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestEmailsDetail:
    """GET /api/v1/emails/{id} — detail with classification_history."""

    async def test_detail_includes_classification_history(
        self, client, auth_headers, seed_data
    ):
        """GET /api/v1/emails/{id} returns email with classification_history."""
        response = await client.get(
            "/api/v1/emails/email-1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "email-1"
        assert "classification_history" in data
        assert len(data["classification_history"]) >= 1
        history = data["classification_history"][0]
        assert history["id"] == "ch-1"
        assert history["category"] == "cliente"
        assert history["confidence"] == 0.95
        assert history["method"] == "rule_engine"

    async def test_detail_not_found(self, client, auth_headers):
        """GET /api/v1/emails/{id} with unknown id returns 404."""
        response = await client.get(
            "/api/v1/emails/non-existent-id", headers=auth_headers
        )
        assert response.status_code == 404
