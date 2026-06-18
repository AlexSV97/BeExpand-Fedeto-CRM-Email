"""Live smoke tests against a real OTRS/Znuny instance.

These talk to a REAL OTRS/Znuny. They are **skipped automatically** unless
`OTRS_ZNUNY_BASE_URL` and `OTRS_ZNUNY_API_TOKEN` are set, so CI (which has no
credentials) never runs them. By default they are **read-only**.

How to run (with credentials in the environment / .env):

    cd backend
    OTRS_ZNUNY_BASE_URL=... OTRS_ZNUNY_API_TOKEN=... \
        pytest tests/smoke -m smoke -v

Optional env vars:
    OTRS_SMOKE_TICKET_ID        a known ticket id → enables the get_ticket check
    OTRS_SMOKE_WRITE_TICKET_ID  a ticket id to write an internal note to (WRITE)
    OTRS_SMOKE_ALLOW_WRITE      must be "1"/"true"/"yes" to allow the write test

The write test is **double-gated** (both the ticket id and the allow flag) because
writing an article to a real OTRS ticket is an outward-facing, hard-to-reverse
action. It posts an internal (non customer-visible) note clearly tagged as a smoke
test.
"""

from __future__ import annotations

import os

import pytest

from src.domain.ticketing import Article, ArticleDraft, Queue, Ticket
from src.integrations.otrs_znuny import OtrsZnunyClient, OtrsZnunySettings
from src.domain.ticketing import ActorKind

_SETTINGS = OtrsZnunySettings()

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not _SETTINGS.is_configured,
        reason="OTRS not configured (set OTRS_ZNUNY_BASE_URL + OTRS_ZNUNY_API_TOKEN)",
    ),
]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


async def _client() -> OtrsZnunyClient:
    return OtrsZnunyClient(settings=_SETTINGS)


# ── Read-only checks ────────────────────────────────────────────────────────


async def test_health_check_ok():
    client = await _client()
    try:
        assert await client.health_check() is True, "OTRS health check failed — check base_url/token"
    finally:
        await client.close()


async def test_list_queues_returns_queues():
    client = await _client()
    try:
        queues = await client.list_queues()
    finally:
        await client.close()
    assert isinstance(queues, list)
    for q in queues:
        assert isinstance(q, Queue)
        assert q.name


async def test_list_tickets_returns_tickets():
    client = await _client()
    try:
        tickets = await client.list_tickets(limit=5)
    finally:
        await client.close()
    assert isinstance(tickets, list)
    for t in tickets:
        assert isinstance(t, Ticket)
        assert t.id


async def test_get_ticket_by_id():
    ticket_id = os.getenv("OTRS_SMOKE_TICKET_ID")
    if not ticket_id:
        pytest.skip("Set OTRS_SMOKE_TICKET_ID to exercise get_ticket")
    client = await _client()
    try:
        ticket = await client.get_ticket(ticket_id)
    finally:
        await client.close()
    assert isinstance(ticket, Ticket)
    assert ticket.id == ticket_id


# ── Write check (double-gated, outward-facing) ──────────────────────────────


async def test_add_internal_note_article():
    write_ticket_id = os.getenv("OTRS_SMOKE_WRITE_TICKET_ID")
    if not write_ticket_id or not _truthy(os.getenv("OTRS_SMOKE_ALLOW_WRITE")):
        pytest.skip(
            "Write smoke disabled — set OTRS_SMOKE_WRITE_TICKET_ID and "
            "OTRS_SMOKE_ALLOW_WRITE=1 to post a real internal note"
        )
    client = await _client()
    draft = ArticleDraft(
        author_kind=ActorKind.SYSTEM,
        author_name="Aiuken SOC smoke",
        subject="[SMOKE TEST] connectivity check",
        body_text="Automated Aiuken SOC live smoke test — internal note, safe to ignore.",
        is_visible_to_customer=False,
    )
    try:
        article = await client.add_article(write_ticket_id, draft)
    finally:
        await client.close()
    assert isinstance(article, Article)
    assert article.ticket_id == write_ticket_id or article.id
