"""Tests for SLA-05 — Early SLA alerts (SlaAlertService + endpoints)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.db.models import OperationalRecord
from src.domain.ticketing import SLA, Queue, Ticket, TicketState
from src.services.sla_alerts import SLA_ALERT_RECORD_KIND, SlaAlertService
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


def _ticket(tid: str, minutes_ago: int, sol: int = 480, sla: bool = True) -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id=tid,
        subject=f"Subject {tid}",
        queue=Queue(name="N1 - Triage", slug="n1-triage"),
        state=TicketState.OPEN,  # RUNNING → SLA clock active
        created_at=now - timedelta(minutes=minutes_ago),
        updated_at=now,
        sla=SLA(name="Standard SLA", solution_time_minutes=sol) if sla else None,
    )


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestScan:
    async def test_at_risk_ticket_raises_alert(self, session):
        svc = SlaAlertService(session)
        alerts = await svc.scan([_ticket("T-HIGH", minutes_ago=400)])  # ratio ~0.17 → high
        assert len(alerts) == 1
        assert alerts[0].risk_level == "high"
        assert alerts[0].severity == "high"

    async def test_healthy_ticket_no_alert(self, session):
        svc = SlaAlertService(session)
        alerts = await svc.scan([_ticket("T-LOW", minutes_ago=10)])  # ratio ~0.98 → low
        assert alerts == []

    async def test_rescan_does_not_duplicate(self, session):
        svc = SlaAlertService(session)
        t = _ticket("T-HIGH", minutes_ago=400)
        first = await svc.scan([t])
        second = await svc.scan([t])
        assert len(first) == 1
        assert second == []
        rows = (
            await session.execute(
                OperationalRecord.__table__.select().where(
                    OperationalRecord.record_kind == SLA_ALERT_RECORD_KIND
                )
            )
        ).fetchall()
        assert len(rows) == 1

    async def test_risk_escalation_creates_new_alert(self, session):
        svc = SlaAlertService(session)
        t = _ticket("T-1", minutes_ago=200)  # ratio ~0.58 → watch
        first = await svc.scan([t])
        assert first[0].risk_level == "watch"

        # Escalate: same ticket now older → high
        t.created_at = datetime.now(timezone.utc) - timedelta(minutes=400)
        second = await svc.scan([t])
        assert len(second) == 1
        assert second[0].risk_level == "high"

    async def test_ticket_without_sla_skipped(self, session):
        svc = SlaAlertService(session)
        alerts = await svc.scan([_ticket("T-NOSLA", minutes_ago=400, sla=False)])
        assert alerts == []

    async def test_acknowledge_removes_from_active(self, session):
        svc = SlaAlertService(session)
        alerts = await svc.scan([_ticket("T-HIGH", minutes_ago=400)])
        alert_id = alerts[0].id

        assert len(await svc.list_active()) == 1
        ok = await svc.acknowledge(alert_id, actor="admin")
        assert ok is True
        assert await svc.list_active() == []

    async def test_acknowledge_unknown_returns_false(self, session):
        svc = SlaAlertService(session)
        assert await svc.acknowledge("does-not-exist", actor="admin") is False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class TestSlaAlertEndpoints:
    async def test_scan_then_list(self, client, auth_headers):
        scan = await client.post("/api/v1/soc/sla/alerts/scan", headers=auth_headers)
        assert scan.status_code == 200
        data = scan.json()
        assert "scanned" in data and "generated" in data and "alerts" in data
        assert data["scanned"] > 0

        listed = await client.get("/api/v1/soc/sla/alerts", headers=auth_headers)
        assert listed.status_code == 200
        assert listed.json()["total"] == len(listed.json()["alerts"])

    async def test_rescan_is_idempotent(self, client, auth_headers):
        first = await client.post("/api/v1/soc/sla/alerts/scan", headers=auth_headers)
        second = await client.post("/api/v1/soc/sla/alerts/scan", headers=auth_headers)
        assert second.json()["generated"] <= first.json()["generated"]

    async def test_ack_unknown_returns_404(self, client, auth_headers):
        resp = await client.post("/api/v1/soc/sla/alerts/nope/ack", headers=auth_headers)
        assert resp.status_code == 404

    async def test_requires_auth(self, client):
        assert (await client.get("/api/v1/soc/sla/alerts")).status_code == 401
        assert (await client.post("/api/v1/soc/sla/alerts/scan")).status_code == 401
