"""
Formal tests for the Dashboard API (Task 5.8).

Covers:
- GET /api/v1/dashboard/summary with seeded data → KPIs
- GET /api/v1/dashboard/summary with empty DB → zeros / empty dicts
"""


class TestDashboardSummary:
    """GET /api/v1/dashboard/summary — aggregate KPIs."""

    async def test_summary_with_seeded_data(self, client, auth_headers, seed_data):
        """GET /summary returns KPIs reflecting seeded test entities."""
        response = await client.get(
            "/api/v1/dashboard/summary", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Structural fields
        assert "total_emails" in data
        assert "emails_today" in data
        assert "contacts_by_category" in data
        assert "opportunities_by_stage" in data

        # With seed data: 1 email, 1 contact (cliente), 1 opportunity (nueva)
        assert data["total_emails"] >= 1
        assert data["contacts_by_category"].get("cliente", 0) >= 1
        assert data["opportunities_by_stage"].get("nueva", 0) >= 1

    async def test_summary_with_empty_db(self, client, auth_headers):
        """GET /summary with no data returns zeros and empty dicts."""
        response = await client.get(
            "/api/v1/dashboard/summary", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 0
        assert data["emails_today"] == 0
        assert data["contacts_by_category"] == {}
        assert data["opportunities_by_stage"] == {}
