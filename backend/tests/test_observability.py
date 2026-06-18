"""Tests for RP-04 — Observability snapshot (ObservabilityService + endpoint)."""

import pytest

from src.db.models import OperationalRecord
from src.services.observability import ObservabilityService
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


async def _add(session, kind: str, status: str = "ok"):
    session.add(OperationalRecord(record_kind=kind, status=status, title=f"{kind}-{status}"))
    await session.commit()


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestSnapshot:
    async def test_integrations_and_mode(self, session):
        snap = await ObservabilityService(session).snapshot()
        names = {i.name: i.status for i in snap.integrations}
        assert names["database"] == "ok"
        assert names["otrs"] == "not_configured"  # no OTRS env in tests
        assert "ai" in names
        assert snap.operatingMode == "demo"

    async def test_record_counts(self, session):
        await _add(session, "escalation")
        await _add(session, "escalation")
        await _add(session, "ownership")
        snap = await ObservabilityService(session).snapshot()
        assert snap.recordCounts.get("escalation") == 2
        assert snap.recordCounts.get("ownership") == 1

    async def test_failures_counted(self, session):
        await _add(session, "audit_event", status="failure")
        await _add(session, "audit_event", status="ok")
        snap = await ObservabilityService(session).snapshot()
        assert snap.failures >= 1

    async def test_intervals_present(self, session):
        snap = await ObservabilityService(session).snapshot()
        assert isinstance(snap.autoSyncIntervalSeconds, int)
        assert isinstance(snap.slaAlertScanIntervalSeconds, int)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestObservabilityEndpoint:
    async def test_endpoint_returns_snapshot(self, client, auth_headers):
        resp = await client.get("/api/v1/reporting/observability", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        for key in ("generatedAt", "operatingMode", "integrations", "recordCounts", "failures"):
            assert key in data
        assert isinstance(data["integrations"], list)

    async def test_endpoint_requires_auth(self, client):
        resp = await client.get("/api/v1/reporting/observability")
        assert resp.status_code == 401
