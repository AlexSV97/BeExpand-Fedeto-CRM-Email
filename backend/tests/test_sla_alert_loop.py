"""Tests for SLA-05 auto-scan wiring (_run_sla_scan_once / _sla_alert_loop)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.api.main import _run_sla_scan_once, _sla_alert_loop
from src.domain.ticketing import SLA, Queue, Ticket, TicketState
from src.services.sla_alerts import SLA_ALERT_RECORD_KIND
from src.db.models import OperationalRecord
from tests.conftest import TestSession


def _ticket(tid: str, minutes_ago: int) -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id=tid,
        subject=f"Subject {tid}",
        queue=Queue(name="N1 - Triage", slug="n1-triage"),
        state=TicketState.OPEN,
        created_at=now - timedelta(minutes=minutes_ago),
        updated_at=now,
        sla=SLA(name="Standard SLA", solution_time_minutes=480),
    )


class TestRunScanOnce:
    async def test_scans_injected_tickets(self):
        async def source():
            return [_ticket("T-HIGH", 400), _ticket("T-LOW", 5)]

        generated = await _run_sla_scan_once(session_factory=TestSession, ticket_source=source)
        assert generated == 1  # only the at-risk one

        async with TestSession() as s:
            rows = (
                await s.execute(
                    OperationalRecord.__table__.select().where(
                        OperationalRecord.record_kind == SLA_ALERT_RECORD_KIND
                    )
                )
            ).fetchall()
        assert len(rows) == 1

    async def test_idempotent_across_runs(self):
        async def source():
            return [_ticket("T-HIGH", 400)]

        first = await _run_sla_scan_once(session_factory=TestSession, ticket_source=source)
        second = await _run_sla_scan_once(session_factory=TestSession, ticket_source=source)
        assert first == 1
        assert second == 0  # dedup


class TestLoopDisabled:
    async def test_loop_returns_immediately_when_disabled(self, monkeypatch):
        # Default setting is 0 (disabled) → loop must return without sleeping.
        await asyncio.wait_for(_sla_alert_loop(), timeout=2.0)
