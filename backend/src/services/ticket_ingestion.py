"""Ticket ingestion service for Aiuken SOC over OTRS/Znuny."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import (
    ActorKind,
    Article,
    ArticleDraft,
    ExternalRef,
    Queue,
    Ticket,
    TicketCreateRequest,
    TicketIngestionInput,
    TicketPriority,
    TicketState,
)
from src.integrations.otrs_znuny import OtrsZnunyClient, OtrsZnunySettings


EmailTicketIngestionInput = TicketIngestionInput


class TicketIngestionService:
    def __init__(
        self,
        client: OtrsZnunyClient | None = None,
        settings: OtrsZnunySettings | None = None,
    ) -> None:
        self._settings = settings or OtrsZnunySettings()
        self._client = client or OtrsZnunyClient(settings=self._settings)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    def _default_queue(self) -> Queue:
        return Queue(name=self._settings.default_queue)

    @staticmethod
    def _clean_metadata(metadata: dict) -> dict:
        return {key: value for key, value in metadata.items() if value is not None}

    def build_ticket_create_request(
        self,
        inbound: EmailTicketIngestionInput,
    ) -> TicketCreateRequest:
        queue = inbound.queue or self._default_queue()
        metadata = self._clean_metadata(
            {
                **inbound.metadata,
                "source": "email",
                "message_id": inbound.message_id,
                "received_at": inbound.received_at.isoformat() if inbound.received_at else None,
                "recipients": inbound.recipients,
            }
        )

        article = ArticleDraft(
            author_kind=ActorKind.HUMAN,
            author_name=inbound.sender_name,
            author_email=inbound.sender_email,
            subject=inbound.subject,
            body_text=inbound.body_text,
            body_html=inbound.body_html,
            is_visible_to_customer=True,
            metadata=self._clean_metadata(
                {
                    "message_id": inbound.message_id,
                    "received_at": inbound.received_at.isoformat() if inbound.received_at else None,
                }
            ),
        )

        return TicketCreateRequest(
            subject=inbound.subject,
            queue=queue,
            state=inbound.state,
            priority=inbound.priority,
            customer_email=inbound.sender_email,
            articles=[article],
            metadata=metadata,
        )

    def build_comment_article(self, inbound: EmailTicketIngestionInput) -> ArticleDraft | None:
        if not inbound.comment_text:
            return None
        return ArticleDraft(
            author_kind=ActorKind.SYSTEM,
            author_name=self._settings.ai_actor_name,
            subject=inbound.subject,
            body_text=inbound.comment_text,
            is_visible_to_customer=inbound.comment_visible_to_customer,
            metadata=self._clean_metadata(
                {
                    "message_id": inbound.message_id,
                    "source": "ingestion-comment",
                }
            ),
        )

    async def ingest_email(self, inbound: EmailTicketIngestionInput) -> Ticket:
        request = self.build_ticket_create_request(inbound)
        ticket = await self._client.create_ticket(request)

        if ticket.external_ref("otrs_znuny", "ticket") is None:
            ticket.external_refs.append(
                ExternalRef(
                    system="otrs_znuny",
                    entity_type="ticket",
                    external_id=ticket.id,
                )
            )

        comment = self.build_comment_article(inbound)
        if comment is not None:
            article = await self._client.add_article(ticket.id, comment)
            ticket.articles.append(article)

        return ticket

    async def update_ticket(self, ticket_id: str, *, state: TicketState | None = None, priority: TicketPriority | None = None) -> Ticket:
        return await self._client.update_ticket(ticket_id, state=state, priority=priority)


async def get_ticket_ingestion_service() -> AsyncIterator[TicketIngestionService]:
    service = TicketIngestionService()
    try:
        yield service
    finally:
        await service.aclose()
