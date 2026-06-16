from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api.main import app
from src.services.agent_governance import AgentGovernanceService
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService
from src.services.queue_strategy import QueueStrategyService
from src.services.ticket_lifecycle import TicketLifecycleService


@pytest.mark.asyncio
async def test_agent_recommendation_and_approval_endpoints(client, auth_headers):
    service = AgentGovernanceService(
        queue_strategy=QueueStrategyService(),
        ticket_lifecycle=TicketLifecycleService(
            now_provider=lambda: datetime(2026, 6, 16, 10, 45, tzinfo=timezone.utc)
        ),
        knowledge_vault=KnowledgeVaultService(
            [
                KnowledgeDocument(
                    id="case-1",
                    title="Root cause analysis for timeout on printer workflow",
                    body="Similar case resolved after a hotfix and customer update.",
                    document_type="case",
                    customer="Aiuken",
                    tags=["timeout", "hotfix"],
                )
            ]
        ),
    )
    app.state.agent_governance_service = service

    response = await client.post(
        "/api/v1/agents/recommendation",
        json={
            "subject": "Need root cause analysis for recurring timeout",
            "body_text": "The timeout needs engineering review and a hotfix.",
            "customer": "Aiuken",
            "current_tier": "n1",
            "current_state": "open",
            "sla_minutes": 60,
            "ticket_created_at": "2026-06-16T10:00:00Z",
            "requested_action": "escalate",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"]["requires_approval"] is True
    assert payload["approval"]["status"] == "pending"
    assert payload["items"][0]["agent"] == "triage"
    assert payload["items"][0]["details"]["queue"] == "N3 - Ingeniería"

    approval_response = await client.post(
        "/api/v1/agents/approvals",
        json={
            "recommendation_id": payload["recommendation_id"],
            "decision": "approve",
            "approver_name": "Analyst One",
            "comment": "Reviewed and approved.",
        },
        headers=auth_headers,
    )

    assert approval_response.status_code == 200
    approval_payload = approval_response.json()
    assert approval_payload["status"] == "approved"
    assert approval_payload["approved_by"] == "Analyst One"

    audit_response = await client.get("/api/v1/agents/audit", headers=auth_headers)
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["total"] == 2
    assert [event["action"] for event in audit_payload["items"]] == [
        "agent.recommendation.created",
        "agent.approval.approved",
    ]

    history_response = await client.get("/api/v1/agents/history", headers=auth_headers)
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["total"] >= 2
    assert {item["record_kind"] for item in history_payload["items"]} >= {
        "agent_recommendation",
        "agent_approval",
    }
