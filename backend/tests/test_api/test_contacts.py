"""
Formal tests for the Contacts API (Task 5.5).

Covers:
- GET list with pagination
- GET list with category filter
- GET list with search (name/email)
- GET contact detail
- PATCH contact category
"""


class TestContactsList:
    """GET /api/v1/contacts — list with filters."""

    async def test_list_paginated(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts returns paginated list with items/total/skip/limit."""
        response = await client.get(
            "/api/v1/contacts?skip=0&limit=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["name"] == "John Doe"

    async def test_list_with_category_filter(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts?category=cliente filters by category."""
        response = await client.get(
            "/api/v1/contacts?category=cliente", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["category"] == "cliente"

    async def test_list_with_search_by_name(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts?search=John finds by name."""
        response = await client.get(
            "/api/v1/contacts?search=John", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["items"][0]["name"] == "John Doe"

    async def test_list_with_search_by_email(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts?search=john@test.com finds by email."""
        response = await client.get(
            "/api/v1/contacts?search=john@test.com", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["items"][0]["email"] == "john@test.com"

    async def test_list_empty_result(self, client, auth_headers):
        """GET /api/v1/contacts with no data returns empty list."""
        response = await client.get(
            "/api/v1/contacts?skip=0&limit=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestContactsDetail:
    """GET /api/v1/contacts/{id} — detail."""

    async def test_get_detail(self, client, auth_headers, seed_data):
        """GET /api/v1/contacts/{id} returns contact detail."""
        response = await client.get(
            "/api/v1/contacts/contact-1", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "contact-1"
        assert data["name"] == "John Doe"
        assert data["email"] == "john@test.com"
        assert data["category"] == "cliente"

    async def test_detail_not_found(self, client, auth_headers):
        """GET /api/v1/contacts/{id} with unknown id returns 404."""
        response = await client.get(
            "/api/v1/contacts/non-existent", headers=auth_headers
        )
        assert response.status_code == 404


class TestContactsPatch:
    """PATCH /api/v1/contacts/{id} — partial update."""

    async def test_patch_category(self, client, auth_headers, seed_data):
        """PATCH /api/v1/contacts/{id} updates category successfully."""
        response = await client.patch(
            "/api/v1/contacts/contact-1",
            headers=auth_headers,
            json={"category": "lead"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "lead"
        # Other fields unchanged
        assert data["name"] == "John Doe"
        assert data["email"] == "john@test.com"

    async def test_patch_not_found(self, client, auth_headers):
        """PATCH /api/v1/contacts/{id} with unknown id returns 404."""
        response = await client.patch(
            "/api/v1/contacts/non-existent",
            headers=auth_headers,
            json={"category": "lead"},
        )
        assert response.status_code == 404
