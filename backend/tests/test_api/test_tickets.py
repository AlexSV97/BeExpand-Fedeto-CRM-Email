"""Formal tests for the ticket ingestion API."""

from src.api.main import app
from src.api.routers.tickets import get_ticket_ingestion_service
from src.domain.ticketing import Queue, Ticket, TicketPriority, TicketState


class FakeTicketIngestionService:
    def __init__(self) -> None:
        self.last_request = None

    async def ingest_email(self, request):
        self.last_request = request
        return Ticket(
            id="TCK-200",
            subject=request.subject,
            queue=Queue(name="Support"),
            state=TicketState.OPEN,
            priority=TicketPriority.HIGH,
            customer_email=request.sender_email,
            external_refs=[
                {
                    "system": "otrs_znuny",
                    "entity_type": "ticket",
                    "external_id": "TCK-200",
                }
            ],
        )


class TestTicketIngestionAPI:
    async def test_ingest_email_returns_created_ticket(self, client, auth_headers):
        service = FakeTicketIngestionService()

        async def override_service():
            yield service

        app.dependency_overrides[get_ticket_ingestion_service] = override_service
        try:
            response = await client.post(
                "/api/v1/tickets/ingest",
                headers=auth_headers,
                json={
                    "subject": "Access issue",
                    "body_text": "I cannot log in",
                    "sender_name": "Alice",
                    "sender_email": "alice@example.com",
                    "priority": "high",
                },
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "TCK-200"
        assert data["external_refs"][0]["external_id"] == "TCK-200"
        assert service.last_request.sender_email == "alice@example.com"
