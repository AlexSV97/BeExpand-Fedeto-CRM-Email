"""Tests for CE-01 — Queue topology (QueueSyncService, DB-backed strategy,
ActionExecutor queue validation).

Uses the shared in-memory SQLite engine from conftest (the autouse setup_db
fixture creates/drops Base.metadata around each test, including the new
``queues`` table).
"""

from unittest.mock import AsyncMock

import pytest

from src.agents.action_executor import ActionExecutor
from src.db.models import QueueModel
from src.domain.ticketing import Queue
from src.services.queue_strategy import QueueStrategyService, QueueTier
from src.services.queue_sync import QueueSyncService
from tests.conftest import TestSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


def _make_otrs_client(queues):
    client = AsyncMock()
    client.list_queues = AsyncMock(return_value=queues)
    return client


# ---------------------------------------------------------------------------
# ensure_seeded (REQ-5, Scenario 3)
# ---------------------------------------------------------------------------


class TestEnsureSeeded:
    async def test_seeds_six_topology_rows(self, session):
        sync = QueueSyncService(session)
        await sync.ensure_seeded()

        rows = (await session.execute(QueueModel.__table__.select())).fetchall()
        assert len(rows) == 6

    async def test_seed_has_correct_parent_child_links(self, session):
        sync = QueueSyncService(session)
        await sync.ensure_seeded()

        fabricante = await sync.get_by_name("Special - Fabricante")
        n3 = await sync.get_by_name("N3 - Ingeniería")
        seguridad = await sync.get_by_name("Special - Seguridad")
        n2 = await sync.get_by_name("N2 - Resolución")

        assert fabricante.parent_id == n3.id
        assert seguridad.parent_id == n2.id

    async def test_ensure_seeded_is_idempotent(self, session):
        sync = QueueSyncService(session)
        await sync.ensure_seeded()
        await sync.ensure_seeded()

        rows = (await session.execute(QueueModel.__table__.select())).fetchall()
        assert len(rows) == 6


# ---------------------------------------------------------------------------
# get_topology (Scenario 1)
# ---------------------------------------------------------------------------


class TestGetTopology:
    async def test_topology_from_db_has_roots_and_specials(self, session):
        sync = QueueSyncService(session)
        await sync.ensure_seeded()

        topology = await sync.get_topology()

        assert [n.tier for n in topology.roots] == [
            QueueTier.N1,
            QueueTier.N2,
            QueueTier.N3,
        ]
        assert len(topology.special_queues) == 3
        assert all(n.tier == QueueTier.SPECIAL for n in topology.special_queues)

    async def test_topology_nodes_expose_parent_slug(self, session):
        sync = QueueSyncService(session)
        await sync.ensure_seeded()

        topology = await sync.get_topology()
        fabricante = next(
            n for n in topology.special_queues if n.name == "Special - Fabricante"
        )
        assert fabricante.queue.parent_id == "n3-ingenieria"


# ---------------------------------------------------------------------------
# sync_from_otrs (REQ-2, Scenario 2, NFR-2) + fallback (Scenario 3)
# ---------------------------------------------------------------------------


class TestSyncFromOtrs:
    async def test_sync_upserts_otrs_queues(self, session):
        otrs = _make_otrs_client(
            [
                Queue(id="10", name="N1 - Triage", slug="n1-triage", tier="n1"),
                Queue(id="20", name="N2 - Resolución", slug="n2-resolucion", tier="n2"),
            ]
        )
        sync = QueueSyncService(session, otrs_client=otrs)

        count = await sync.sync_from_otrs()

        assert count == 2
        n1 = await sync.get_by_name("N1 - Triage")
        assert n1 is not None
        assert n1.otrs_external_id == "10"

    async def test_sync_is_idempotent(self, session):
        otrs = _make_otrs_client(
            [Queue(id="10", name="N1 - Triage", slug="n1-triage", tier="n1")]
        )
        sync = QueueSyncService(session, otrs_client=otrs)

        await sync.sync_from_otrs()
        await sync.sync_from_otrs()

        rows = (
            await session.execute(
                QueueModel.__table__.select().where(QueueModel.name == "N1 - Triage")
            )
        ).fetchall()
        assert len(rows) == 1

    async def test_sync_infers_parent_for_known_specials(self, session):
        otrs = _make_otrs_client(
            [
                Queue(id="3", name="N3 - Ingeniería", slug="n3-ingenieria", tier="n3"),
                Queue(id="4", name="Special - Fabricante", slug="special-fabricante", tier="special"),
            ]
        )
        sync = QueueSyncService(session, otrs_client=otrs)
        await sync.sync_from_otrs()

        fabricante = await sync.get_by_name("Special - Fabricante")
        n3 = await sync.get_by_name("N3 - Ingeniería")
        assert fabricante.parent_id == n3.id

    async def test_sync_falls_back_to_seed_when_otrs_unreachable(self, session):
        otrs = AsyncMock()
        otrs.list_queues = AsyncMock(side_effect=ConnectionError("OTRS down"))
        sync = QueueSyncService(session, otrs_client=otrs)

        count = await sync.sync_from_otrs()

        assert count == 0
        rows = (await session.execute(QueueModel.__table__.select())).fetchall()
        assert len(rows) == 6


# ---------------------------------------------------------------------------
# DB-backed QueueStrategyService (REQ-3, Scenario 5) + backward compat
# ---------------------------------------------------------------------------


class TestQueueStrategyDbBacked:
    async def test_create_loads_topology_from_db(self, session):
        service = await QueueStrategyService.create(session)
        topology = service.topology()

        names = {n.name for n in topology.roots}
        assert {"N1 - Triage", "N2 - Resolución", "N3 - Ingeniería"} == names

    async def test_recommend_routes_incident_to_n2_from_db_topology(self, session):
        from src.services.queue_strategy import QueueDecisionRequest

        service = await QueueStrategyService.create(session)
        decision = service.recommend(
            QueueDecisionRequest(
                subject="Critical incident",
                body_text="There is an error and a timeout in production",
            )
        )
        assert decision.routing.tier == QueueTier.N2
        assert decision.routing.queue.name == "N2 - Resolución"

    def test_no_arg_constructor_keeps_hardcoded_topology(self):
        service = QueueStrategyService()
        assert len(service.topology().roots) == 3


# ---------------------------------------------------------------------------
# ActionExecutor queue validation (REQ-4, Scenarios 4 & 6)
# ---------------------------------------------------------------------------


class TestActionExecutorValidateQueue:
    async def test_validates_existing_queue(self, session):
        await QueueSyncService(session).ensure_seeded()
        # Support is a business queue not in the 6-row seed; add it explicitly.
        session.add(QueueModel(name="Support", slug="support", is_active=True))
        await session.commit()

        executor = ActionExecutor(db=session)
        resolved = await executor._validate_queue(Queue(name="Support"))
        assert resolved.name == "Support"
        assert resolved.id is not None

    async def test_unknown_queue_falls_back_to_default(self, session):
        await QueueSyncService(session).ensure_seeded()

        executor = ActionExecutor(db=session)
        resolved = await executor._validate_queue(Queue(name="NonExistentQueue"))
        assert resolved.name == "Support"  # OtrsZnunySettings.default_queue

    async def test_inactive_queue_falls_back_to_default(self, session):
        session.add(QueueModel(name="Archived", slug="archived", is_active=False))
        await session.commit()

        executor = ActionExecutor(db=session)
        resolved = await executor._validate_queue(Queue(name="Archived"))
        assert resolved.name == "Support"
