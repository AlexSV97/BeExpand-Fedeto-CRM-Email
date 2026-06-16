from datetime import datetime, timezone

import pytest

from src.domain.ticketing import (
    ActorKind,
    Article,
    ExternalRef,
    Queue,
    Ticket,
    TicketPriority,
    TicketState,
)
from src.services.ticket_ingestion import (
    EmailTicketIngestionInput,
    TicketIngestionService,
)


class FakeOtrsConnector:
    def __init__(self) -> None:
        self.created_requests = []
        self.added_articles = []
        self.updated_tickets = []

    async def create_ticket(self, request):
        self.created_requests.append(request)
        return Ticket(
            id="TCK-100",
            subject=request.subject,
            queue=request.queue,
            state=request.state,
            priority=request.priority,
            customer_email=request.customer_email,
            articles=[],
        )

    async def add_article(self, ticket_id: str, article):
        self.added_articles.append((ticket_id, article))
        return Article(
            id="ART-200",
            ticket_id=ticket_id,
            author_kind=article.author_kind,
            author_name=article.author_name,
            author_email=article.author_email,
            subject=article.subject,
            body_text=article.body_text,
            body_html=article.body_html,
            is_visible_to_customer=article.is_visible_to_customer,
        )

    async def update_ticket(self, ticket_id: str, **kwargs):
        self.updated_tickets.append((ticket_id, kwargs))
        return Ticket(
            id=ticket_id,
            subject="Updated",
            queue=Queue(name="Support"),
        )

    async def close(self):
        return None


def test_build_ticket_request_from_email_input_maps_canonical_payload():
    service = TicketIngestionService(client=FakeOtrsConnector())
    inbound = EmailTicketIngestionInput(
        subject="Access issue",
        body_text="I cannot log in",
        body_html="<p>I cannot log in</p>",
        sender_name="Alice",
        sender_email="alice@example.com",
        recipients=["support@example.com"],
        message_id="msg-1",
        received_at=datetime(2026, 6, 16, 10, 30, tzinfo=timezone.utc),
        priority=TicketPriority.HIGH,
        state=TicketState.OPEN,
        metadata={"channel": "email"},
    )

    request = service.build_ticket_create_request(inbound)

    assert request.subject == "Access issue"
    assert request.queue.name == "Support"
    assert request.customer_email == "alice@example.com"
    assert request.priority is TicketPriority.HIGH
    assert request.state is TicketState.OPEN
    assert request.articles[0].author_kind is ActorKind.HUMAN
    assert request.articles[0].author_email == "alice@example.com"
    assert request.metadata["message_id"] == "msg-1"
    assert request.metadata["recipients"] == ["support@example.com"]


@pytest.mark.asyncio
async def test_ingest_email_creates_ticket_adds_comment_and_returns_external_ref():
    connector = FakeOtrsConnector()
    service = TicketIngestionService(client=connector)
    inbound = EmailTicketIngestionInput(
        subject="Access issue",
        body_text="I cannot log in",
        sender_name="Alice",
        sender_email="alice@example.com",
        comment_text="Internal follow-up needed",
        comment_visible_to_customer=False,
    )

    ticket = await service.ingest_email(inbound)

    assert connector.created_requests[0].subject == "Access issue"
    assert connector.added_articles[0][0] == "TCK-100"
    assert connector.added_articles[0][1].is_visible_to_customer is False
    assert ticket.external_ref("otrs_znuny", "ticket").external_id == "TCK-100"
    assert ticket.articles[0].id == "ART-200"


@pytest.mark.asyncio
async def test_ingest_email_without_comment_skips_add_article():
    connector = FakeOtrsConnector()
    service = TicketIngestionService(client=connector)
    inbound = EmailTicketIngestionInput(
        subject="Access issue",
        body_text="I cannot log in",
        sender_name="Alice",
        sender_email="alice@example.com",
    )

    ticket = await service.ingest_email(inbound)

    assert connector.created_requests[0].subject == "Access issue"
    assert connector.added_articles == []
    assert ticket.external_ref("otrs_znuny", "ticket").external_id == "TCK-100"
