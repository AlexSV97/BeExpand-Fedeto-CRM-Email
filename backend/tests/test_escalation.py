"""Tests for CE-03 — N-level escalation (EscalationService + endpoint)."""

import pytest

from src.services.escalation import (
    EscalationRequest,
    EscalationService,
)
from src.services.queue_strategy import QueueStrategyService, QueueTier


def _service() -> EscalationService:
    return EscalationService(QueueStrategyService())  # hardcoded topology


# ---------------------------------------------------------------------------
# Unit — escalate()
# ---------------------------------------------------------------------------


class TestEscalate:
    def test_auto_escalation_goes_one_level_up(self):
        plan = _service().escalate(EscalationRequest(current_tier=QueueTier.N1))
        assert plan.should_escalate is True
        assert plan.to_tier == QueueTier.N2
        assert plan.level == 2

    def test_explicit_target_with_multilevel_path(self):
        plan = _service().escalate(
            EscalationRequest(current_tier=QueueTier.N1, target_tier=QueueTier.N3)
        )
        assert plan.to_tier == QueueTier.N3
        assert plan.level == 3
        assert [s.tier for s in plan.steps] == [QueueTier.N2, QueueTier.N3]

    def test_target_not_higher_is_noop(self):
        plan = _service().escalate(
            EscalationRequest(current_tier=QueueTier.N2, target_tier=QueueTier.N1)
        )
        assert plan.should_escalate is False
        assert plan.to_tier == QueueTier.N2

    def test_target_equal_is_noop(self):
        plan = _service().escalate(
            EscalationRequest(current_tier=QueueTier.N2, target_tier=QueueTier.N2)
        )
        assert plan.should_escalate is False

    def test_top_tier_is_noop(self):
        plan = _service().escalate(EscalationRequest(current_tier=QueueTier.N3))
        assert plan.should_escalate is False
        assert plan.to_tier == QueueTier.N3

    def test_resolves_current_tier_from_slug(self):
        plan = _service().escalate(
            EscalationRequest(current_queue_slug="n2-resolucion")
        )
        assert plan.from_tier == QueueTier.N2
        assert plan.to_tier == QueueTier.N3

    def test_unknown_slug_defaults_to_n1(self):
        plan = _service().escalate(
            EscalationRequest(current_queue_slug="does-not-exist")
        )
        assert plan.from_tier == QueueTier.N1
        assert plan.to_tier == QueueTier.N2

    def test_to_queue_matches_target_tier(self):
        plan = _service().escalate(EscalationRequest(current_tier=QueueTier.N1))
        assert plan.to_queue.slug == "n2-resolucion"

    def test_single_level_has_one_step(self):
        plan = _service().escalate(EscalationRequest(current_tier=QueueTier.N1))
        assert [s.tier for s in plan.steps] == [QueueTier.N2]


# ---------------------------------------------------------------------------
# Endpoint — POST /queues/escalate
# ---------------------------------------------------------------------------


class TestEscalateEndpoint:
    async def test_endpoint_returns_plan(self, client, auth_headers):
        response = await client.post(
            "/api/v1/queues/escalate",
            headers=auth_headers,
            json={"current_tier": "n1", "target_tier": "n3", "reason": "x"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["should_escalate"] is True
        assert data["to_tier"] == "n3"
        assert data["level"] == 3
        assert len(data["steps"]) == 2

    async def test_endpoint_requires_auth(self, client):
        response = await client.post(
            "/api/v1/queues/escalate",
            json={"current_tier": "n1"},
        )
        assert response.status_code in (401, 403)
