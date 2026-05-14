"""
Formal tests for the Opportunities API (Task 5.6).

Covers full CRUD cycle:
- POST create, GET list, GET detail, PUT update, DELETE
- GET list with stage filter
"""


class TestOpportunitiesCRUD:
    """Full CRUD cycle for /api/v1/opportunities."""

    async def test_create_opportunity(self, client, auth_headers, seed_data):
        """POST /api/v1/opportunities creates and returns the opportunity."""
        response = await client.post(
            "/api/v1/opportunities",
            headers=auth_headers,
            json={
                "contact_id": "contact-1",
                "title": "New Deal",
                "stage": "nueva",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Deal"
        assert data["stage"] == "nueva"
        assert data["contact_id"] == "contact-1"
        assert "id" in data
        assert "created_at" in data

    async def test_list_opportunities(self, client, auth_headers, seed_data):
        """GET /api/v1/opportunities returns paginated list."""
        response = await client.get(
            "/api/v1/opportunities?skip=0&limit=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["items"][0]["id"] == "opp-1"

    async def test_list_with_stage_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/opportunities?stage=nueva filters by stage."""
        response = await client.get(
            "/api/v1/opportunities?stage=nueva", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["stage"] == "nueva"

    async def test_list_empty_with_mismatched_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/opportunities with non-matching stage returns empty."""
        response = await client.get(
            "/api/v1/opportunities?stage=cerrada_ganada", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_get_opportunity_detail(self, client, auth_headers, seed_data):
        """GET /api/v1/opportunities/{id} returns detail."""
        response = await client.get(
            "/api/v1/opportunities/opp-1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "opp-1"
        assert data["title"] == "Test Opportunity"
        assert data["stage"] == "nueva"

    async def test_update_opportunity(self, client, auth_headers, seed_data):
        """PUT /api/v1/opportunities/{id} updates the opportunity."""
        response = await client.put(
            "/api/v1/opportunities/opp-1",
            headers=auth_headers,
            json={
                "contact_id": "contact-1",
                "title": "Updated Deal",
                "stage": "calificada",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Deal"
        assert data["stage"] == "calificada"

    async def test_delete_opportunity(self, client, auth_headers, seed_data):
        """DELETE /api/v1/opportunities/{id} removes and returns 204."""
        response = await client.delete(
            "/api/v1/opportunities/opp-1", headers=auth_headers
        )
        assert response.status_code == 204

        # Verify deleted
        get_resp = await client.get(
            "/api/v1/opportunities/opp-1", headers=auth_headers
        )
        assert get_resp.status_code == 404

    async def test_detail_not_found(self, client, auth_headers):
        """GET /api/v1/opportunities/{id} with unknown id returns 404."""
        response = await client.get(
            "/api/v1/opportunities/non-existent", headers=auth_headers
        )
        assert response.status_code == 404
