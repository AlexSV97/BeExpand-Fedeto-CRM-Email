"""Tests for CE-05 — Ticket ownership & lock (TicketOwnershipService + endpoints)."""

import pytest

from src.db.models import OperationalRecord
from src.services.ticket_ownership import (
    OWNERSHIP_RECORD_KIND,
    TicketOwnershipService,
)
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestOwnershipService:
    async def test_assign_sets_owner(self, session):
        svc = TicketOwnershipService(session)
        await svc.assign("TICKET-1", owner="alice", actor_name="admin")

        state = await svc.current_state("TICKET-1")
        assert state.owner == "alice"
        rows = (
            await session.execute(
                OperationalRecord.__table__.select().where(
                    OperationalRecord.record_kind == OWNERSHIP_RECORD_KIND
                )
            )
        ).fetchall()
        assert len(rows) == 1

    async def test_lock_sets_locked_and_locked_by(self, session):
        svc = TicketOwnershipService(session)
        await svc.assign("TICKET-1", owner="alice", actor_name="admin")
        await svc.lock("TICKET-1", actor_name="bob")

        state = await svc.current_state("TICKET-1")
        assert state.locked is True
        assert state.locked_by == "bob"
        assert state.owner == "alice"  # preserved

    async def test_unlock_clears_lock_keeps_owner(self, session):
        svc = TicketOwnershipService(session)
        await svc.assign("TICKET-1", owner="alice", actor_name="admin")
        await svc.lock("TICKET-1", actor_name="bob")
        await svc.unlock("TICKET-1", actor_name="bob")

        state = await svc.current_state("TICKET-1")
        assert state.locked is False
        assert state.locked_by is None
        assert state.owner == "alice"

    async def test_current_state_is_latest_change(self, session):
        svc = TicketOwnershipService(session)
        await svc.assign("TICKET-1", owner="alice", actor_name="admin")
        await svc.lock("TICKET-1", actor_name="bob")
        await svc.unlock("TICKET-1", actor_name="bob")

        history = await svc.list_history("TICKET-1")
        assert len(history) == 3
        assert (await svc.current_state("TICKET-1")).locked is False

    async def test_empty_default_for_unknown_ticket(self, session):
        svc = TicketOwnershipService(session)
        state = await svc.current_state("TICKET-9")
        assert state.owner is None
        assert state.locked is False
        assert state.locked_by is None

    async def test_lock_without_prior_owner_defaults_to_actor(self, session):
        svc = TicketOwnershipService(session)
        await svc.lock("TICKET-1", actor_name="carol")
        state = await svc.current_state("TICKET-1")
        assert state.owner == "carol"
        assert state.locked_by == "carol"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class TestOwnershipEndpoints:
    async def test_assign_then_get_ownership(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/assign",
            headers=auth_headers,
            json={"owner": "alice", "reason": "owns the case"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"]["owner"] == "alice"

        got = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/ownership",
            headers=auth_headers,
        )
        assert got.status_code == 200
        data = got.json()
        assert data["state"]["owner"] == "alice"
        assert len(data["history"]) >= 1

    async def test_lock_unlock_cycle(self, client, auth_headers):
        await client.post("/api/v1/soc/tickets/TICKET-1000/lock", headers=auth_headers, json={})
        locked = await client.get("/api/v1/soc/tickets/TICKET-1000/ownership", headers=auth_headers)
        assert locked.json()["state"]["locked"] is True

        await client.post("/api/v1/soc/tickets/TICKET-1000/unlock", headers=auth_headers, json={})
        unlocked = await client.get("/api/v1/soc/tickets/TICKET-1000/ownership", headers=auth_headers)
        assert unlocked.json()["state"]["locked"] is False

    async def test_assign_rejects_empty_owner(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/assign",
            headers=auth_headers,
            json={"owner": "  "},
        )
        assert resp.status_code == 422

    async def test_ownership_requires_auth(self, client):
        resp = await client.get("/api/v1/soc/tickets/TICKET-1000/ownership")
        assert resp.status_code == 401
