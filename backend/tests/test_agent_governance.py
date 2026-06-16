from __future__ import annotations

from datetime import datetime, timezone

from src.domain.ticketing import TicketState
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService
from src.services.queue_strategy import QueueStrategyService, QueueTier
from src.services.ticket_lifecycle import TicketLifecycleService


def _service() -> object:
    return None


def test_recommendation_combines_specialized_agents_and_requires_approval_for_escalation():
    from src.services.agent_governance import (
        AgentGovernanceService,
        AgentRecommendationRequest,
        AgentKind,
        ApprovalStatus,
    )

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

    response = service.recommend(
        AgentRecommendationRequest(
            subject="Need root cause analysis for recurring timeout",
            body_text="The timeout needs engineering review and a hotfix.",
            customer="Aiuken",
            current_tier=QueueTier.N1,
            current_state=TicketState.OPEN,
            sla_minutes=60,
            ticket_created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
            requested_action="escalate",
        )
    )

    agent_names = [item.agent for item in response.items]
    assert agent_names == [
        AgentKind.TRIAGE,
        AgentKind.SLA,
        AgentKind.KNOWLEDGE,
        AgentKind.RESPONSE,
        AgentKind.ESCALATION,
        AgentKind.COMPLIANCE,
    ]
    assert response.items[0].details["queue"] == "N3 - Ingeniería"
    assert response.items[1].details["risk_level"] == "high"
    assert response.items[2].details["top_case_id"] == "case-1"
    assert "case-1" in response.items[3].summary
    assert response.policy.requires_approval is True
    assert response.policy.reason
    assert response.approval is not None
    assert response.approval.status is ApprovalStatus.PENDING


def test_recommendation_keeps_simple_review_flow_auto_approved():
    from src.services.agent_governance import AgentGovernanceService, AgentRecommendationRequest, ApprovalStatus

    service = AgentGovernanceService(
        queue_strategy=QueueStrategyService(),
        ticket_lifecycle=TicketLifecycleService(
            now_provider=lambda: datetime(2026, 6, 16, 10, 10, tzinfo=timezone.utc)
        ),
        knowledge_vault=KnowledgeVaultService(),
    )

    response = service.recommend(
        AgentRecommendationRequest(
            subject="How do I access the portal?",
            body_text="Simple access question for the portal.",
            current_tier=QueueTier.N1,
            current_state=TicketState.NEW,
            requested_action="review",
        )
    )

    assert response.items[0].details["queue"] == "N1 - Triage"
    assert response.policy.requires_approval is False
    assert response.approval is not None
    assert response.approval.status is ApprovalStatus.AUTO_APPROVED


def test_approval_updates_pending_recommendation_and_audit_log():
    from src.services.agent_governance import (
        AgentGovernanceService,
        AgentApprovalRequest,
        AgentRecommendationRequest,
        ApprovalDecision,
        ApprovalStatus,
    )

    service = AgentGovernanceService(
        queue_strategy=QueueStrategyService(),
        ticket_lifecycle=TicketLifecycleService(
            now_provider=lambda: datetime(2026, 6, 16, 10, 45, tzinfo=timezone.utc)
        ),
        knowledge_vault=KnowledgeVaultService(),
    )

    recommendation = service.recommend(
        AgentRecommendationRequest(
            subject="Need engineering escalation for outage",
            body_text="The issue needs a hotfix before customer impact grows.",
            current_tier=QueueTier.N1,
            current_state=TicketState.OPEN,
            sla_minutes=30,
            ticket_created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
            requested_action="escalate",
        )
    )

    approved = service.approve(
        AgentApprovalRequest(
            recommendation_id=recommendation.recommendation_id,
            decision=ApprovalDecision.APPROVE,
            approver_name="Analyst One",
            comment="Reviewed and approved.",
        )
    )

    assert approved.status is ApprovalStatus.APPROVED
    assert approved.approved_by == "Analyst One"
    assert approved.comment == "Reviewed and approved."

    audit_actions = [event.action for event in service.audit_log()]
    assert audit_actions == ["agent.recommendation.created", "agent.approval.approved"]
