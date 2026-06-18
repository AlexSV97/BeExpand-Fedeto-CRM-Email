"""Tests for CE-06 — External escalation (ExternalEscalationService + endpoints)."""

import pytest

from src.db.models import OperationalRecord
from src.services.external_escalation import (
    EXTERNAL_ESCALATION_RECORD_KIND,
    ExternalEscalationService,
)
from src.services.queue_strategy import QueueStrategyService
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


def _svc(session) -> ExternalEscalationService:
    return ExternalEscalationService(session, QueueStrategyService())


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestExternalEscalationService:
    async def test_manufacturer_resolves_special_queue(self, session):
        result = await _svc(session).escalate(
            ticket_id="TICKET-1", destination="fabricante", actor_name="admin"
        )
        assert result.queue_slug == "special-fabricante"
        assert result.tracking_ref.system == "fabricante"
        assert result.tracking_ref.external_id  # non-empty

    async def test_uses_provided_external_id(self, session):
        result = await _svc(session).escalate(
            ticket_id="TICKET-1", destination="external_itsm",
            actor_name="admin", external_id="SNOW-123",
        )
        assert result.tracking_ref.external_id == "SNOW-123"
        assert result.tracking_ref.system == "external_itsm"
        assert result.queue_slug == "special-external-itsm"

    async def test_generates_external_id_when_missing(self, session):
        result = await _svc(session).escalate(
            ticket_id="TICKET-1", destination="fabricante", actor_name="admin"
        )
        assert result.tracking_ref.external_id.startswith("FAB-")

    async def test_persists_and_lists(self, session):
        svc = _svc(session)
        await svc.escalate(ticket_id="TICKET-1", destination="fabricante", actor_name="admin")
        rows = (
            await session.execute(
                OperationalRecord.__table__.select().where(
                    OperationalRecord.record_kind == EXTERNAL_ESCALATION_RECORD_KIND
                )
            )
        ).fetchall()
        assert len(rows) == 1
        history = await svc.list_for_ticket("TICKET-1")
        assert len(history) == 1

    async def test_unknown_destination_raises(self, session):
        with pytest.raises(ValueError):
            await _svc(session).escalate(
                ticket_id="TICKET-1", destination="nope", actor_name="admin"
            )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class TestExternalEscalationEndpoints:
    async def test_escalate_external_then_history(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate-external",
            headers=auth_headers,
            json={"destination": "fabricante", "reason": "vendor bug"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["queue_slug"] == "special-fabricante"
        assert data["tracking_ref"]["external_id"]

        hist = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/external-escalations",
            headers=auth_headers,
        )
        assert hist.status_code == 200
        h = hist.json()
        assert h["total"] >= 1
        assert h["items"][0]["queue_slug"] == "special-fabricante"

    async def test_unknown_destination_rejected(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate-external",
            headers=auth_headers,
            json={"destination": "nope"},
        )
        assert resp.status_code == 422

    async def test_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate-external",
            json={"destination": "fabricante"},
        )
        assert resp.status_code == 401
