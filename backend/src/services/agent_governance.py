from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.models import AuditActorKind, AuditEvent, AuditOutcome
from src.db.models import OperationalRecord
from src.domain.ticketing import Queue, SLA, Ticket, TicketState
from src.services.knowledge_vault import KnowledgeVaultService, SimilarCaseRequest
from src.services.queue_strategy import QueueDecisionRequest, QueueStrategyService, QueueTier
from src.services.ticket_lifecycle import TicketLifecycleService


class AgentKind(str, Enum):
    TRIAGE = "triage"
    SLA = "sla"
    KNOWLEDGE = "knowledge"
    RESPONSE = "response"
    ESCALATION = "escalation"
    COMPLIANCE = "compliance"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class AgentRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body_text: str
    customer: str | None = None
    current_tier: QueueTier = QueueTier.N1
    current_state: TicketState = TicketState.NEW
    sla_minutes: int | None = None
    ticket_created_at: datetime | None = None
    ticket_updated_at: datetime | None = None
    requested_action: str = "review"
    knowledge_limit: int = 3


class AgentRecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentKind
    summary: str
    reason: str
    confidence: float
    requires_approval: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_approval: bool
    reason: str
    critical_actions: list[str] = Field(default_factory=list)


class AgentApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    recommendation_id: str
    status: ApprovalStatus
    requested_at: datetime
    approved_by: str | None = None
    rejected_by: str | None = None
    decided_at: datetime | None = None
    comment: str | None = None


class AgentRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    items: list[AgentRecommendationItem]
    policy: GovernancePolicyDecision
    approval: AgentApprovalRecord | None = None


class AgentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    decision: ApprovalDecision
    approver_name: str
    comment: str | None = None


class AgentAuditTrail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEvent]


class AgentGovernanceService:
    def __init__(
        self,
        *,
        queue_strategy: QueueStrategyService | None = None,
        ticket_lifecycle: TicketLifecycleService | None = None,
        knowledge_vault: KnowledgeVaultService | None = None,
    ) -> None:
        self._queue_strategy = queue_strategy or QueueStrategyService()
        self._ticket_lifecycle = ticket_lifecycle or TicketLifecycleService()
        self._knowledge_vault = knowledge_vault or KnowledgeVaultService()
        self._recommendations: dict[str, dict[str, Any]] = {}
        self._approvals: dict[str, AgentApprovalRecord] = {}
        self._audit_events: list[AuditEvent] = []

    def recommend(self, request: AgentRecommendationRequest) -> AgentRecommendationResponse:
        recommendation_id = str(uuid4())
        triage = self._triage(request)
        sla = self._sla(request, triage)
        knowledge = self._knowledge(request)
        response = self._response(request, triage, knowledge)
        escalation = self._escalation(request, triage)
        compliance = self._compliance(request, triage, escalation)

        items = [triage, sla, knowledge, response, escalation, compliance]
        policy = self._policy(request, items)
        approval = self._create_approval(recommendation_id, policy.requires_approval)

        self._recommendations[recommendation_id] = {
            "request": request,
            "items": items,
            "policy": policy,
            "approval_id": approval.id,
        }

        self._audit_events.append(
            AuditEvent(
                actor_kind=AuditActorKind.SYSTEM,
                actor_name="agent-governance",
                action="agent.recommendation.created",
                resource_type="agent_recommendation",
                resource_id=recommendation_id,
                outcome=AuditOutcome.SUCCESS,
                details={
                    "requires_approval": policy.requires_approval,
                    "critical_actions": policy.critical_actions,
                    "queue": triage.details.get("queue"),
                    "requested_action": request.requested_action,
                },
            )
        )

        return AgentRecommendationResponse(
            recommendation_id=recommendation_id,
            items=items,
            policy=policy,
            approval=approval,
        )

    def approve(self, request: AgentApprovalRequest) -> AgentApprovalRecord:
        record = self._lookup_approval(request.recommendation_id)
        now = datetime.now(timezone.utc)

        if request.decision is ApprovalDecision.APPROVE:
            record.status = ApprovalStatus.APPROVED
            record.approved_by = request.approver_name
            record.rejected_by = None
            self._audit_events.append(
                AuditEvent(
                    actor_kind=AuditActorKind.HUMAN,
                    actor_name=request.approver_name,
                    action="agent.approval.approved",
                    resource_type="agent_recommendation",
                    resource_id=request.recommendation_id,
                    outcome=AuditOutcome.SUCCESS,
                    details={"comment": request.comment or ""},
                )
            )
        else:
            record.status = ApprovalStatus.REJECTED
            record.rejected_by = request.approver_name
            record.approved_by = None
            self._audit_events.append(
                AuditEvent(
                    actor_kind=AuditActorKind.HUMAN,
                    actor_name=request.approver_name,
                    action="agent.approval.rejected",
                    resource_type="agent_recommendation",
                    resource_id=request.recommendation_id,
                    outcome=AuditOutcome.SKIPPED,
                    details={"comment": request.comment or ""},
                )
            )

        record.decided_at = now
        record.comment = request.comment
        self._approvals[request.recommendation_id] = record
        return record

    def audit_log(self) -> list[AuditEvent]:
        return list(self._audit_events)

    def log_event(
        self,
        actor_name: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record a human-driven audit event (e.g. note added, reclassification, escalation)."""
        event = AuditEvent(
            actor_kind=AuditActorKind.HUMAN,
            actor_name=actor_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=AuditOutcome.SUCCESS,
            details=details or {},
        )
        self._audit_events.append(event)
        return event

    async def persist_recommendation(
        self,
        db: AsyncSession,
        recommendation_id: str,
        request: AgentRecommendationRequest,
        response: AgentRecommendationResponse,
    ) -> OperationalRecord:
        record = OperationalRecord(
            record_kind="agent_recommendation",
            resource_id=recommendation_id,
            actor_kind="system",
            actor_name="agent-governance",
            status="pending" if response.policy.requires_approval else "auto_approved",
            title=f"Agent recommendation for {request.subject}",
            payload={
                "request": request.model_dump(mode="json"),
                "response": response.model_dump(mode="json"),
            },
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def persist_approval(
        self,
        db: AsyncSession,
        request: AgentApprovalRequest,
        record: AgentApprovalRecord,
    ) -> OperationalRecord:
        result = await db.execute(
            select(OperationalRecord).where(
                OperationalRecord.record_kind == "agent_recommendation",
                OperationalRecord.resource_id == request.recommendation_id,
            )
        )
        recommendation = result.scalar_one_or_none()
        payload = {
            "approval_request": request.model_dump(mode="json"),
            "approval_record": record.model_dump(mode="json"),
        }
        if recommendation is not None:
            recommendation.status = record.status.value
            recommendation.payload = {
                **(recommendation.payload or {}),
                "approval": payload,
            }

        persisted = OperationalRecord(
            record_kind="agent_approval",
            resource_id=request.recommendation_id,
            actor_kind="human",
            actor_name=request.approver_name,
            status=record.status.value,
            title=f"Approval for {request.recommendation_id}",
            payload=payload,
        )
        db.add(persisted)
        await db.commit()
        await db.refresh(persisted)
        return persisted

    async def persist_audit_event(self, db: AsyncSession, event: AuditEvent) -> OperationalRecord:
        record = OperationalRecord(
            record_kind="audit_event",
            resource_id=event.resource_id,
            actor_kind=event.actor_kind.value,
            actor_name=event.actor_name,
            status=event.outcome.value,
            title=event.action,
            payload=event.model_dump(mode="json"),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def list_history(self, db: AsyncSession, limit: int = 20) -> list[OperationalRecord]:
        result = await db.execute(
            select(OperationalRecord)
            .where(OperationalRecord.record_kind.in_(["agent_recommendation", "agent_approval", "audit_event"]))
            .order_by(OperationalRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _triage(self, request: AgentRecommendationRequest) -> AgentRecommendationItem:
        decision = self._queue_strategy.recommend(
            QueueDecisionRequest(
                subject=request.subject,
                body_text=request.body_text,
                urgency="media",
                current_tier=request.current_tier,
                current_locked=False,
            )
        )
        return AgentRecommendationItem(
            agent=AgentKind.TRIAGE,
            summary=f"Route to {decision.routing.queue.name} owned by {decision.routing.owner}.",
            reason=decision.routing.reason,
            confidence=decision.routing.confidence,
            requires_approval=decision.routing.lock,
            details={
                "queue": decision.routing.queue.name,
                "tier": decision.routing.tier.value,
                "owner": decision.routing.owner,
                "lock": decision.routing.lock,
            },
        )

    def _sla(self, request: AgentRecommendationRequest, triage: AgentRecommendationItem) -> AgentRecommendationItem:
        now = self._now()
        created_at = request.ticket_created_at or now
        updated_at = request.ticket_updated_at or created_at
        queue_name = str(triage.details.get("queue", "Governed Queue"))
        ticket = Ticket(
            id=request.customer or "ticket-governance",
            subject=request.subject,
            queue=Queue(name=queue_name),
            state=request.current_state,
            sla=(
                SLA(name="Governed SLA", solution_time_minutes=request.sla_minutes)
                if request.sla_minutes is not None
                else None
            ),
            created_at=created_at,
            updated_at=updated_at,
        )
        assessment = self._ticket_lifecycle.assess(ticket, as_of=now)
        return AgentRecommendationItem(
            agent=AgentKind.SLA,
            summary=assessment.recommendation,
            reason=assessment.reason,
            confidence=0.9 if assessment.risk_level.value in {"high", "critical"} else 0.72,
            requires_approval=assessment.risk_level.value == "critical",
            details={
                "risk_level": assessment.risk_level.value,
                "remaining_minutes": assessment.remaining_minutes,
                "stop_sla": assessment.stop_sla,
            },
        )

    def _knowledge(self, request: AgentRecommendationRequest) -> AgentRecommendationItem:
        result = self._knowledge_vault.similar_cases(
            SimilarCaseRequest(
                subject=request.subject,
                body_text=request.body_text,
                customer=request.customer,
                limit=request.knowledge_limit,
            )
        )
        if result.items:
            top = result.items[0]
            summary = f"Top similar case {top.document.id}: {top.document.title}."
            details = {
                "top_case_id": top.document.id,
                "top_case_title": top.document.title,
                "matched_terms": top.matched_terms,
            }
            reason = top.explanation
            confidence = min(0.95, 0.6 + (top.score / 10.0))
        else:
            summary = "No similar case found in the knowledge vault."
            details = {"top_case_id": None, "top_case_title": None, "matched_terms": []}
            reason = "Knowledge vault returned no deterministic match."
            confidence = 0.45
        return AgentRecommendationItem(
            agent=AgentKind.KNOWLEDGE,
            summary=summary,
            reason=reason,
            confidence=confidence,
            details=details,
        )

    def _response(
        self,
        request: AgentRecommendationRequest,
        triage: AgentRecommendationItem,
        knowledge: AgentRecommendationItem,
    ) -> AgentRecommendationItem:
        if knowledge.details.get("top_case_title"):
            summary = (
                f"Draft response for {request.subject}: reference {knowledge.details['top_case_id']} "
                f"and keep the case aligned with {triage.details['queue']}."
            )
        else:
            summary = f"Draft response for {request.subject}: acknowledge the request and confirm next steps."
        return AgentRecommendationItem(
            agent=AgentKind.RESPONSE,
            summary=summary,
            reason="Response draft stays deterministic and references the selected evidence.",
            confidence=0.8 if knowledge.details.get("top_case_id") else 0.55,
            details={
                "mentions_case": knowledge.details.get("top_case_id"),
                "queue": triage.details.get("queue"),
            },
        )

    def _escalation(self, request: AgentRecommendationRequest, triage: AgentRecommendationItem) -> AgentRecommendationItem:
        current_rank = self._tier_rank(request.current_tier)
        routing_rank = self._tier_rank(QueueTier(triage.details["tier"]))
        should_escalate = routing_rank > current_rank
        summary = (
            f"Escalate from {request.current_tier.value} to {triage.details['tier']}."
            if should_escalate
            else f"Keep the case at {request.current_tier.value}."
        )
        return AgentRecommendationItem(
            agent=AgentKind.ESCALATION,
            summary=summary,
            reason="Escalation follows the deterministic tier comparison.",
            confidence=0.92 if should_escalate else 0.61,
            requires_approval=should_escalate,
            details={
                "should_escalate": should_escalate,
                "from_tier": request.current_tier.value,
                "to_tier": triage.details["tier"],
            },
        )

    def _compliance(
        self,
        request: AgentRecommendationRequest,
        triage: AgentRecommendationItem,
        escalation: AgentRecommendationItem,
    ) -> AgentRecommendationItem:
        sensitive_terms = ("password", "token", "security", "breach", "pii", "privacy")
        text = f"{request.subject} {request.body_text}".lower()
        flagged_terms = [term for term in sensitive_terms if term in text]
        requires_approval = bool(flagged_terms) or bool(escalation.details.get("should_escalate"))
        reason = (
            "Sensitive content or escalation path needs human review."
            if requires_approval
            else "No compliance blockers found."
        )
        return AgentRecommendationItem(
            agent=AgentKind.COMPLIANCE,
            summary=reason,
            reason=reason,
            confidence=0.96 if requires_approval else 0.74,
            requires_approval=requires_approval,
            details={
                "flagged_terms": flagged_terms,
                "requires_approval": requires_approval,
                "queue": triage.details.get("queue"),
            },
        )

    def _policy(
        self,
        request: AgentRecommendationRequest,
        items: list[AgentRecommendationItem],
    ) -> GovernancePolicyDecision:
        critical_actions = [
            item.agent.value
            for item in items
            if item.requires_approval
        ]
        requested_action = request.requested_action.strip().lower()
        explicit_critical = requested_action in {"escalate", "writeback", "close", "notify"}
        requires_approval = explicit_critical or bool(critical_actions)
        if requires_approval:
            if explicit_critical:
                reason = f"Requested action '{requested_action}' is critical and must be approved."
            else:
                reason = f"{', '.join(critical_actions)} require human approval before execution."
        else:
            reason = "The recommendation is informational and can be auto-accepted."
        return GovernancePolicyDecision(
            requires_approval=requires_approval,
            reason=reason,
            critical_actions=critical_actions,
        )

    def _create_approval(self, recommendation_id: str, requires_approval: bool) -> AgentApprovalRecord:
        status = ApprovalStatus.PENDING if requires_approval else ApprovalStatus.AUTO_APPROVED
        record = AgentApprovalRecord(
            id=str(uuid4()),
            recommendation_id=recommendation_id,
            status=status,
            requested_at=self._now(),
            decided_at=self._now() if status is ApprovalStatus.AUTO_APPROVED else None,
            comment="Auto-approved by deterministic policy" if status is ApprovalStatus.AUTO_APPROVED else None,
        )
        self._approvals[recommendation_id] = record
        return record

    def _lookup_approval(self, recommendation_id: str) -> AgentApprovalRecord:
        if recommendation_id not in self._approvals:
            raise ValueError(f"Unknown recommendation_id: {recommendation_id}")
        return self._approvals[recommendation_id]

    @staticmethod
    def _tier_rank(tier: QueueTier) -> int:
        return {
            QueueTier.N1: 1,
            QueueTier.N2: 2,
            QueueTier.N3: 3,
            QueueTier.SPECIAL: 4,
        }[tier]

    def _now(self) -> datetime:
        now = self._ticket_lifecycle._now_provider()  # deterministic clock from lifecycle service
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now


async def get_agent_governance_service():
    yield AgentGovernanceService()
