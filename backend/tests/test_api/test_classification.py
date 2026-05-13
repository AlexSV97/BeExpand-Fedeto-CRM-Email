"""
Formal tests for the Classification History API (Task 5.7).

Covers:
- GET list with email_id filter
- GET detail by id
"""


class TestClassificationList:
    """GET /api/v1/classification-history — list with filters."""

    async def test_list_by_email_id(self, client, auth_headers, seed_data):
        """GET /api/v1/classification-history?email_id=... returns matching records."""
        response = await client.get(
            "/api/v1/classification-history?email_id=email-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["items"][0]["id"] == "ch-1"
        assert data["items"][0]["category"] == "cliente"

    async def test_list_empty_without_filter(self, client, auth_headers):
        """GET /api/v1/classification-history with no data returns empty."""
        response = await client.get(
            "/api/v1/classification-history", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestClassificationDetail:
    """GET /api/v1/classification-history/{id} — detail."""

    async def test_get_detail(self, client, auth_headers, seed_data):
        """GET /api/v1/classification-history/{id} returns single record."""
        response = await client.get(
            "/api/v1/classification-history/ch-1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "ch-1"
        assert data["email_id"] == "email-1"
        assert data["category"] == "cliente"
        assert data["confidence"] == 0.95
        assert data["method"] == "rule_engine"

    async def test_detail_not_found(self, client, auth_headers):
        """GET /api/v1/classification-history/{id} with unknown id returns 404."""
        response = await client.get(
            "/api/v1/classification-history/non-existent",
            headers=auth_headers,
        )
        assert response.status_code == 404
