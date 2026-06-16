from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from src.audit.models import AuditActorKind, AuditEvent, AuditOutcome
from src.domain.ticketing import (
    ActorKind,
    Article,
    ExternalRef,
    Queue,
    SLA,
    Ticket,
    TicketPriority,
    TicketState,
)
from src.integrations.otrs_znuny.client import OtrsZnunyClient
from src.integrations.otrs_znuny.settings import OtrsZnunySettings


def _ticket_payload(ticket_id: str = "TCK-1") -> dict:
    return {
        "id": ticket_id,
        "subject": "Printer does not work",
        "queue": {
            "id": "q-1",
            "name": "Support",
            "slug": "support",
            "external_refs": [
                {
                    "system": "otrs",
                    "entity_type": "queue",
                    "external_id": "Queue::Support",
                }
            ],
        },
        "state": "open",
        "priority": "normal",
        "customer_email": "customer@example.com",
        "sla": {
            "id": "sla-1",
            "name": "Standard",
            "response_time_minutes": 60,
            "solution_time_minutes": 480,
        },
        "articles": [
            {
                "id": "a-1",
                "ticket_id": ticket_id,
                "author_kind": "human",
                "author_name": "Support Agent",
                "author_email": "agent@example.com",
                "subject": "Re: Printer does not work",
                "body_text": "We're checking it now.",
            }
        ],
        "external_refs": [
            {
                "system": "otrs",
                "entity_type": "ticket",
                "external_id": ticket_id,
            },
            {
                "system": "znuny",
                "entity_type": "ticket",
                "external_id": f"ZN-{ticket_id}",
            },
        ],
    }


def test_ticket_primitives_keep_nested_domain_shape():
    queue = Queue(
        id="q-1",
        name="Support",
        slug="support",
        external_refs=[
            ExternalRef(system="otrs", entity_type="queue", external_id="Queue::Support")
        ],
    )
    sla = SLA(
        id="sla-1",
        name="Standard",
        response_time_minutes=60,
        solution_time_minutes=480,
    )
    ticket = Ticket(
        id="t-1",
        subject="Need help",
        queue=queue,
        state=TicketState.OPEN,
        priority=TicketPriority.NORMAL,
        customer_email="customer@example.com",
        sla=sla,
        articles=[
            Article(
                id="a-1",
                ticket_id="t-1",
                author_kind=ActorKind.HUMAN,
                author_name="Human Agent",
                body_text="Hello",
            )
        ],
        external_refs=[
            ExternalRef(system="otrs", entity_type="ticket", external_id="123"),
            ExternalRef(system="znuny", entity_type="ticket", external_id="456"),
        ],
    )

    assert ticket.queue.name == "Support"
    assert ticket.articles[0].author_kind is ActorKind.HUMAN
    assert ticket.external_ref("znuny").external_id == "456"
    assert ticket.primary_external_ref().external_id == "123"


def test_ticket_primitives_return_none_when_external_ref_missing():
    ticket = Ticket(
        id="t-2",
        subject="Need help",
        queue=Queue(name="Support"),
    )

    assert ticket.external_ref("otrs") is None
    assert ticket.primary_external_ref() is None


def test_ticket_primitives_reject_unknown_fields():
    with pytest.raises(ValidationError):
        Queue(name="Support", slug="support", unexpected="boom")


def test_otrs_settings_build_endpoints_and_headers():
    settings = OtrsZnunySettings(
        base_url="https://otrs.example.com/",
        api_token="secret-token",
        api_prefix="/api/v1",
        timeout_seconds=20.0,
    )

    assert settings.normalized_base_url == "https://otrs.example.com"
    assert settings.tickets_path() == "/api/v1/tickets"
    assert settings.ticket_path("TCK-1") == "/api/v1/tickets/TCK-1"
    assert settings.auth_headers()["Authorization"] == "Bearer secret-token"
    assert settings.auth_headers()["Accept"] == "application/json"


def test_otrs_settings_report_when_not_configured():
    settings = OtrsZnunySettings()

    assert settings.is_configured is False
    assert settings.ticket_path("TCK-1") == "/api/v1/tickets/TCK-1"


@pytest.mark.asyncio
async def test_otrs_connector_list_tickets_parses_collection():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/v1/tickets"
        assert request.url.params["queue"] == "Support"
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json={
                "items": [_ticket_payload("TCK-1"), _ticket_payload("TCK-2")],
            },
        )

    settings = OtrsZnunySettings(base_url="https://otrs.example.com", api_token="secret-token")
    async with OtrsZnunyClient(settings=settings, transport=httpx.MockTransport(handler)) as client:
        tickets = await client.list_tickets(queue="Support", limit=25)

    assert len(tickets) == 2
    assert tickets[0].queue.name == "Support"
    assert tickets[1].external_ref("znuny").external_id == "ZN-TCK-2"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_otrs_connector_get_ticket_parses_single_ticket_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/tickets/TCK-9"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json={"ticket": _ticket_payload("TCK-9")})

    settings = OtrsZnunySettings(base_url="https://otrs.example.com", api_token="secret-token")
    async with OtrsZnunyClient(settings=settings, transport=httpx.MockTransport(handler)) as client:
        ticket = await client.get_ticket("TCK-9")

    assert ticket.id == "TCK-9"
    assert ticket.sla.solution_time_minutes == 480
    assert ticket.articles[0].author_email == "agent@example.com"


def test_audit_event_identifies_human_actor():
    event = AuditEvent(
        actor_kind=AuditActorKind.HUMAN,
        actor_name="Maria",
        action="ticket.viewed",
        resource_type="ticket",
        resource_id="TCK-1",
        outcome=AuditOutcome.SUCCESS,
        details={"channel": "web"},
    )

    assert event.is_human() is True
    assert event.is_ai() is False
    assert event.details["channel"] == "web"


def test_audit_event_identifies_ai_actor():
    event = AuditEvent(
        actor_kind=AuditActorKind.IA,
        actor_name="BeConnect AI",
        action="ticket.summarized",
        resource_type="ticket",
        resource_id="TCK-2",
        outcome=AuditOutcome.SUCCESS,
    )

    assert event.is_ai() is True
    assert event.is_human() is False
    assert event.actor_kind is AuditActorKind.IA
