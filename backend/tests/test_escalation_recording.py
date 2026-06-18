"""Tests for CE-04 — Escalation recording (EscalationRecordService + endpoint)."""

import pytest

from src.db.models import OperationalRecord
from src.services.escalation import EscalationRequest, EscalationService
from src.services.escalation_recording import (
    ESCALATION_RECORD_KIND,
    EscalationRecordService,
)
from src.services.queue_strategy import QueueStrategyService, QueueTier
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


def _plan(current=QueueTier.N1, target=None):
    return EscalationService(QueueStrategyService()).escalate(
        EscalationRequest(current_tier=current, target_tier=target)
    )


# ---------------------------------------------------------------------------
# Unit — record / list
# ---------------------------------------------------------------------------


class TestRecord:
    async def test_record_persists_escalation_row(self, session):
        svc = EscalationRecordService(session)
        await svc.record(ticket_id="TICKET-1", actor_name="alice", plan=_plan())

        rows = (
            await session.execute(
                OperationalRecord.__table__.select().where(
                    OperationalRecord.record_kind == ESCALATION_RECORD_KIND
                )
            )
        ).fetchall()
        assert len(rows) == 1
        record = rows[0]
        assert record.resource_id == "TICKET-1"
        assert record.status == "escalated"

    async def test_noop_plan_recorded_with_noop_status(self, session):
        svc = EscalationRecordService(session)
        # N3 with no target → should_escalate False
        await svc.record(ticket_id="TICKET-1", actor_name="alice", plan=_plan(current=QueueTier.N3))

        records = await svc.list_for_ticket("TICKET-1")
        assert records[0].status == "noop"

    async def test_history_newest_first(self, session):
        # Explicit distinct timestamps: SQLite CURRENT_TIMESTAMP is second-resolution,
        # so two records in the same second would tie. Set created_at directly.
        from datetime import datetime, timedelta, timezone

        base = datetime(2026, 6, 18, 10, 0, 0, tzinfo=timezone.utc)
        older = OperationalRecord(
            record_kind=ESCALATION_RECORD_KIND, resource_id="TICKET-1",
            actor_name="alice", status="escalated", title="older",
            payload={"plan": {}}, created_at=base,
        )
        newer = OperationalRecord(
            record_kind=ESCALATION_RECORD_KIND, resource_id="TICKET-1",
            actor_name="bob", status="escalated", title="newer",
            payload={"plan": {}}, created_at=base + timedelta(minutes=5),
        )
        session.add_all([older, newer])
        await session.commit()

        records = await EscalationRecordService(session).list_for_ticket("TICKET-1")
        assert len(records) == 2
        assert records[0].actor_name == "bob"  # most recent first

    async def test_history_is_ticket_scoped(self, session):
        svc = EscalationRecordService(session)
        await svc.record(ticket_id="TICKET-1", actor_name="alice", plan=_plan())
        await svc.record(ticket_id="TICKET-2", actor_name="bob", plan=_plan())

        records = await svc.list_for_ticket("TICKET-1")
        assert len(records) == 1
        assert records[0].resource_id == "TICKET-1"

    async def test_to_item_maps_plan_fields(self, session):
        svc = EscalationRecordService(session)
        await svc.record(ticket_id="TICKET-1", actor_name="alice", plan=_plan(target=QueueTier.N3))
        record = (await svc.list_for_ticket("TICKET-1"))[0]

        item = EscalationRecordService.to_item(record)
        assert item.ticket_id == "TICKET-1"
        assert item.from_tier == "n1"
        assert item.to_tier == "n3"
        assert item.to_queue == "n3-ingenieria"
        assert item.level == 3
        assert item.should_escalate is True


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestEscalationHistoryEndpoint:
    async def test_escalate_then_history_returns_record(self, client, auth_headers):
        esc = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "Testing recording", "target_tier": "n2"},
        )
        assert esc.status_code == 200

        hist = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/escalations",
            headers=auth_headers,
        )
        assert hist.status_code == 200
        data = hist.json()
        assert data["ticket_id"] == "TICKET-1000"
        assert data["total"] >= 1
        assert data["items"][0]["to_tier"] == "n2"

    async def test_history_requires_auth(self, client):
        response = await client.get("/api/v1/soc/tickets/TICKET-1000/escalations")
        assert response.status_code == 401

    async def test_history_empty_for_unescalated_ticket(self, client, auth_headers):
        response = await client.get(
            "/api/v1/soc/tickets/TICKET-9999/escalations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_recording_failure_does_not_break_escalate(self, client, auth_headers, monkeypatch):
        async def _boom(self, *args, **kwargs):
            raise RuntimeError("recording down")

        monkeypatch.setattr(EscalationRecordService, "record", _boom)

        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "Testing best-effort", "target_tier": "n2"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "escalated"
