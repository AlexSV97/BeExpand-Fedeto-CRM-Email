from __future__ import annotations

import pytest

from src.api.main import app
from src.api.routers.queues import get_queue_strategy_service
from src.services.queue_strategy import (
    QueueDecisionRequest,
    QueueStrategyService,
    QueueTier,
)


def test_queue_topology_exposes_n1_n2_n3_and_special_queues():
    service = QueueStrategyService()

    topology = service.topology()

    root_names = [node.name for node in topology.roots]
    assert root_names == ["N1 - Triage", "N2 - Resolución", "N3 - Ingeniería"]
    special_names = [node.name for node in topology.special_queues]
    assert special_names == [
        "Special - Fabricante",
        "Special - External ITSM",
        "Special - Seguridad",
    ]


def test_recommend_decision_routes_incident_to_n2_and_locks_on_escalation():
    service = QueueStrategyService()

    decision = service.recommend(
        QueueDecisionRequest(
            subject="Printer error after outage",
            body_text="The service error appears during an incident and blocks the queue.",
            urgency="alta",
        )
    )

    assert decision.routing.tier is QueueTier.N2
    assert decision.routing.queue.name == "N2 - Resolución"
    assert decision.routing.owner == "N2 Resolver"
    assert decision.routing.lock is True
    assert "error" in decision.routing.reason.lower()
    assert decision.escalation.should_escalate is True
    assert decision.escalation.from_tier is QueueTier.N1
    assert decision.escalation.to_tier is QueueTier.N2
    assert decision.escalation.lock is True
    assert "sla" in decision.escalation.motivation.lower()


def test_recommend_decision_routes_root_cause_case_to_n3():
    service = QueueStrategyService()

    decision = service.recommend(
        QueueDecisionRequest(
            subject="Need root cause analysis for recurring timeout",
            body_text="We need code-level analysis and a hotfix for the timeout.",
            urgency="alta",
        )
    )

    assert decision.routing.tier is QueueTier.N3
    assert decision.routing.queue.name == "N3 - Ingeniería"
    assert decision.routing.owner == "N3 Engineering"
    assert decision.routing.lock is True
    assert "hotfix" in decision.routing.reason.lower()
    assert decision.escalation.should_escalate is True
    assert decision.escalation.to_tier is QueueTier.N3
    assert decision.escalation.owner == "N3 Engineering"


def test_recommend_decision_routes_vendor_case_to_special_queue():
    service = QueueStrategyService()

    decision = service.recommend(
        QueueDecisionRequest(
            subject="Manufacturer response needed for faulty firmware",
            body_text="The vendor must confirm the firmware incompatibility.",
        )
    )

    assert decision.routing.tier is QueueTier.SPECIAL
    assert decision.routing.queue.name == "Special - Fabricante"
    assert decision.routing.owner == "Vendor Coordinator"
    assert decision.routing.lock is True
    assert "vendor" in decision.routing.reason.lower() or "fabricante" in decision.routing.motivation.lower()
    assert decision.escalation.should_escalate is True
    assert decision.escalation.to_tier is QueueTier.SPECIAL
    assert decision.escalation.lock is True


def test_recommend_decision_keeps_simple_request_in_n1_without_escalation():
    service = QueueStrategyService()

    decision = service.recommend(
        QueueDecisionRequest(
            subject="How do I reset my password?",
            body_text="Simple access question for the portal.",
        )
    )

    assert decision.routing.tier is QueueTier.N1
    assert decision.routing.queue.name == "N1 - Triage"
    assert decision.routing.owner == "N1 Triage"
    assert decision.routing.lock is False
    assert decision.escalation.should_escalate is False
    assert decision.escalation.from_tier is QueueTier.N1
    assert decision.escalation.to_tier is QueueTier.N1
    assert decision.escalation.owner == "N1 Triage"
    assert decision.escalation.lock is False


@pytest.mark.asyncio
async def test_queue_recommendation_api_returns_serialized_decision(client, auth_headers):
    async def override_service():
        yield QueueStrategyService()

    app.dependency_overrides[get_queue_strategy_service] = override_service
    try:
        response = await client.post(
            "/api/v1/queues/recommendation",
            headers=auth_headers,
            json={
                "subject": "Recurring timeout needs engineering review",
                "body_text": "The timeout is reproduced every time and needs a hotfix.",
                "urgency": "alta",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["routing"]["tier"] == "n3"
    assert data["routing"]["queue"]["name"] == "N3 - Ingeniería"
    assert data["escalation"]["should_escalate"] is True
    assert data["escalation"]["lock"] is True
