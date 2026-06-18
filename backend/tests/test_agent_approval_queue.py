"""Tests for AG-07 — Pending agent approval queue."""

import pytest

from src.services.agent_governance import (
    AgentApprovalRequest,
    AgentGovernanceService,
    AgentRecommendationRequest,
    ApprovalDecision,
)
from tests.conftest import TestSession


@pytest.fixture
async def session():
    async with TestSession() as s:
        yield s


async def _persist(svc: AgentGovernanceService, session, subject: str, body: str):
    req = AgentRecommendationRequest(subject=subject, body_text=body)
    resp = svc.recommend(req)
    await svc.persist_recommendation(session, resp.recommendation_id, req, resp)
    return resp


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestPendingApprovals:
    async def test_recommendation_requiring_approval_is_pending(self, session):
        svc = AgentGovernanceService()
        resp = await _persist(svc, session, "Critical incident", "error timeout incident in production")
        assert resp.policy.requires_approval is True  # sanity: this should need approval

        pending = await svc.list_pending_approvals(session)
        assert resp.recommendation_id in [r.resource_id for r in pending]
        assert all(r.status == "pending" for r in pending)

    async def test_auto_approved_not_pending(self, session):
        svc = AgentGovernanceService()
        resp = await _persist(svc, session, "Gracias", "Mensaje rutinario de agradecimiento sin incidencias")
        assert resp.policy.requires_approval is False

        pending = await svc.list_pending_approvals(session)
        assert resp.recommendation_id not in [r.resource_id for r in pending]

    async def test_approving_removes_from_queue(self, session):
        svc = AgentGovernanceService()
        resp = await _persist(svc, session, "Critical incident", "error timeout incident bug failure")
        assert resp.recommendation_id in [r.resource_id for r in await svc.list_pending_approvals(session)]

        approval = AgentApprovalRequest(
            recommendation_id=resp.recommendation_id,
            decision=ApprovalDecision.APPROVE,
            approver_name="admin",
        )
        record = svc.approve(approval)
        await svc.persist_approval(session, approval, record)

        assert resp.recommendation_id not in [r.resource_id for r in await svc.list_pending_approvals(session)]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestPendingApprovalsEndpoint:
    async def test_endpoint_lists_pending(self, client, auth_headers):
        rec = await client.post(
            "/api/v1/agents/recommendation",
            headers=auth_headers,
            json={"subject": "Critical incident", "body_text": "error timeout incident in production"},
        )
        assert rec.status_code == 200
        rec_id = rec.json()["recommendation_id"]

        pend = await client.get("/api/v1/agents/approvals/pending", headers=auth_headers)
        assert pend.status_code == 200
        data = pend.json()
        assert data["total"] >= 1
        assert rec_id in [item["resource_id"] for item in data["items"]]

    async def test_endpoint_requires_auth(self, client):
        resp = await client.get("/api/v1/agents/approvals/pending")
        assert resp.status_code == 401
