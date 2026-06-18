"""Tests for CP-01 — Smart inbox enrichment (_enrich_ticket_item + endpoint)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.api.routers.soc import _enrich_ticket_item
from src.domain.ticketing import SLA, Queue, Ticket, TicketState
from src.services.queue_strategy import QueueStrategyService
from src.services.ticket_lifecycle import TicketLifecycleService

_VALID_RISKS = {"low", "watch", "high", "critical"}
_KNOWN_SLUGS = {"n1-triage", "n2-resolucion", "n3-ingenieria",
                "special-fabricante", "special-external-itsm", "special-seguridad"}


def _ticket(tid: str, minutes_ago: int, sla: bool = True, owner="alice") -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id=tid,
        subject="There is an error and a timeout in production",
        queue=Queue(name="N1 - Triage", slug="n1-triage"),
        state=TicketState.OPEN,
        owner=owner,
        assigned_to=owner,
        created_at=now - timedelta(minutes=minutes_ago),
        updated_at=now,
        sla=SLA(name="Standard SLA", solution_time_minutes=480) if sla else None,
    )


class TestEnrich:
    def test_computes_risk_and_suggested_queue(self):
        item = _enrich_ticket_item(_ticket("T-HIGH", 400), QueueStrategyService(), TicketLifecycleService())
        assert item.slaRisk in _VALID_RISKS
        assert item.slaRemainingMinutes is not None
        assert item.suggestedQueue in _KNOWN_SLUGS
        assert item.owner == "alice"
        assert item.queue == "n1-triage"

    def test_incident_suggests_n2(self):
        # subject has incident/error/timeout keywords → rule engine routes to N2
        item = _enrich_ticket_item(_ticket("T-1", 100), QueueStrategyService(), TicketLifecycleService())
        assert item.suggestedQueue == "n2-resolucion"

    def test_no_sla_means_null_risk(self):
        item = _enrich_ticket_item(_ticket("T-NOSLA", 400, sla=False), QueueStrategyService(), TicketLifecycleService())
        assert item.slaRisk is None
        assert item.slaRemainingMinutes is None
        assert item.suggestedQueue in _KNOWN_SLUGS  # suggestion still works

    def test_resilient_to_assess_failure(self, monkeypatch):
        lifecycle = TicketLifecycleService()
        monkeypatch.setattr(lifecycle, "assess", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        item = _enrich_ticket_item(_ticket("T-1", 400), QueueStrategyService(), lifecycle)
        assert item.slaRisk is None       # failed gracefully
        assert item.id == "T-1"           # row still built


class TestSmartInboxEndpoint:
    async def test_rows_are_enriched(self, client, auth_headers):
        resp = await client.get("/api/v1/soc/tickets", headers=auth_headers)
        assert resp.status_code == 200
        tickets = resp.json()["tickets"]
        assert len(tickets) > 0
        row = tickets[0]
        for field in ("owner", "queue", "slaRisk", "suggestedQueue"):
            assert field in row
        assert row["suggestedQueue"] in _KNOWN_SLUGS

    async def test_filtering_preserved(self, client, auth_headers):
        resp = await client.get("/api/v1/soc/tickets", params={"priority": "high"}, headers=auth_headers)
        assert resp.status_code == 200
        for t in resp.json()["tickets"]:
            assert t["priority"] == "high"
            assert "slaRisk" in t
