"""
Tests for the manual email review endpoint.

PATCH /api/v1/emails/{email_id}/review
- 200: category changed, classification_history entry created
- 404: email not found
- 422: invalid category
"""


class TestReviewEmail:
    """PATCH /api/v1/emails/{id}/review — cambio manual de categoría."""

    async def test_review_updates_category(
        self, client, auth_headers, seed_data
    ):
        """PATCH con categoría válida cambia la categoría del email."""
        response = await client.patch(
            "/api/v1/emails/email-1/review",
            headers=auth_headers,
            json={"category": "lead"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "lead"
        assert data["status"] == "revisado"

    async def test_review_creates_classification_history(
        self, client, auth_headers, seed_data
    ):
        """PATCH crea un registro en classification_history."""
        await client.patch(
            "/api/v1/emails/email-1/review",
            headers=auth_headers,
            json={"category": "proveedor"},
        )

        # Verificar que el historial se creó
        response = await client.get(
            "/api/v1/emails/email-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        histories = [
            h
            for h in data["classification_history"]
            if h["method"] == "manual_review"
        ]
        assert len(histories) == 1
        entry = histories[0]
        assert entry["category"] == "proveedor"
        assert entry["method"] == "manual_review"
        assert entry["reviewed"] is True
        assert entry["reviewed_by"] == "admin"
        assert entry["confidence"] == 1.0

    async def test_review_not_found(
        self, client, auth_headers
    ):
        """PATCH con email_id inexistente devuelve 404."""
        response = await client.patch(
            "/api/v1/emails/non-existent-id/review",
            headers=auth_headers,
            json={"category": "lead"},
        )
        assert response.status_code == 404

    async def test_review_invalid_category(
        self, client, auth_headers, seed_data
    ):
        """PATCH con categoría inválida devuelve 422."""
        response = await client.patch(
            "/api/v1/emails/email-1/review",
            headers=auth_headers,
            json={"category": "invalida"},
        )
        assert response.status_code == 422

    async def test_review_same_category(
        self, client, auth_headers, seed_data
    ):
        """PATCH con misma categoría no causa error (es no-op)."""
        response = await client.patch(
            "/api/v1/emails/email-1/review",
            headers=auth_headers,
            json={"category": "cliente"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "cliente"
        assert data["status"] == "revisado"
