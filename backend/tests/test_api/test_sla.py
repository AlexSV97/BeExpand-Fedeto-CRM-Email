from datetime import datetime, timezone

import pytest

from src.api.main import app
from src.api.routers.sla import get_ticket_lifecycle_service
from src.domain.ticketing import Queue, SLA, Ticket, TicketPriority, TicketState
from src.services.ticket_lifecycle import TicketLifecycleService


@pytest.mark.asyncio
async def test_ticket_sla_status_api_returns_assessment(client, auth_headers):
    fixed_now = datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc)

    async def override_service():
        yield TicketLifecycleService(now_provider=lambda: fixed_now)

    app.dependency_overrides[get_ticket_lifecycle_service] = override_service
    try:
        response = await client.post(
            "/api/v1/tickets/sla/status",
            headers=auth_headers,
            json=Ticket(
                id="TCK-9",
                subject="Printer is down",
                queue=Queue(name="Support"),
                state=TicketState.PENDING,
                priority=TicketPriority.NORMAL,
                sla=SLA(id="SLA-1", name="Standard", solution_time_minutes=60),
                created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 6, 16, 10, 20, tzinfo=timezone.utc),
            ).model_dump(mode="json"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "pending"
    assert data["lifecycle_state"] == "paused"
    assert data["stop_sla"] is True
    assert data["remaining_minutes"] == 40.0
    assert data["risk_level"] == "watch"
