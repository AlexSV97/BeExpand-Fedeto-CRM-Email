"""Tests for CP-05/06 — Ticket drafts (TicketDraftService + endpoint)."""

from datetime import datetime, timezone

import pytest

from src.domain.ticketing import Article, ActorKind, Queue, Ticket, TicketState
from src.services.ticket_drafts import TicketDraftService


class FakeLLM:
    def __init__(self, response: str, model: str = "fake-model"):
        self._response = response
        self.model = model

    async def generate(self, prompt: str, **kwargs) -> str:
        return self._response


class RaisingLLM:
    model = "fake-model"

    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("LLM down")


def _ticket() -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id="TICKET-1",
        subject="No puedo acceder al portal",
        queue=Queue(name="N1 - Triage", slug="n1-triage"),
        state=TicketState.OPEN,
        customer_email="cliente@example.com",
        created_at=now,
        updated_at=now,
        articles=[
            Article(
                id="A1", ticket_id="TICKET-1", author_kind=ActorKind.HUMAN,
                author_name="Cliente", body_text="Llevo una hora sin poder entrar.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestDraft:
    async def test_ai_customer_reply(self):
        svc = TicketDraftService(FakeLLM("Estimado cliente, estamos en ello."))
        res = await svc.draft(_ticket(), "customer_reply")
        assert res.source == "ai"
        assert res.kind == "customer_reply"
        assert res.text == "Estimado cliente, estamos en ello."
        assert res.requires_approval is True
        assert res.model == "fake-model"

    async def test_internal_note_kind(self):
        svc = TicketDraftService(FakeLLM("Nota: revisar logs."))
        res = await svc.draft(_ticket(), "internal_note")
        assert res.kind == "internal_note"
        assert res.source == "ai"

    async def test_fallback_when_llm_raises(self):
        svc = TicketDraftService(RaisingLLM())
        res = await svc.draft(_ticket(), "customer_reply")
        assert res.source == "template"
        assert res.text.strip()  # non-empty
        assert res.requires_approval is True

    async def test_fallback_when_llm_empty(self):
        svc = TicketDraftService(FakeLLM("   "))
        res = await svc.draft(_ticket(), "internal_note")
        assert res.source == "template"
        assert "TICKET-1" in res.text or res.text.strip()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestDraftEndpoint:
    async def test_endpoint_returns_draft(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/draft",
            headers=auth_headers,
            params={"kind": "customer_reply"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "customer_reply"
        assert data["source"] in ("ai", "template")
        assert data["text"].strip()
        assert data["requires_approval"] is True

    async def test_invalid_kind_rejected(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/draft",
            headers=auth_headers,
            params={"kind": "nope"},
        )
        assert resp.status_code == 422

    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/soc/tickets/TICKET-1000/draft")
        assert resp.status_code == 401
