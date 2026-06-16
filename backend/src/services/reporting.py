from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from enum import Enum
from statistics import mean
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import Ticket, TicketState
from src.services.knowledge_vault import KnowledgeDocument
from src.services.ticket_lifecycle import TicketLifecycleService


class ReportWindow(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class FeedbackVerdict(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVISE = "revise"


class ImprovementSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    title: str
    reason: str
    source: str
    priority: str = "medium"
    placeholder: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class OperationalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_tickets: int = 0
    open_tickets: int = 0
    pending_tickets: int = 0
    closed_tickets: int = 0
    merged_tickets: int = 0
    backlog_tickets: int = 0
    paused_tickets: int = 0
    sla_assessed_tickets: int = 0
    sla_at_risk_tickets: int = 0
    sla_breaches: int = 0
    average_elapsed_minutes: float = 0.0
    average_remaining_minutes: float = 0.0
    sla_compliance_rate: float = 0.0
    knowledge_documents: int = 0


class OperationalReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window: ReportWindow
    as_of: datetime | None = None
    tickets: list[Ticket] = Field(default_factory=list)
    knowledge_documents: list[KnowledgeDocument] = Field(default_factory=list)


class OperationalReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime | None = None
    tickets: list[Ticket] = Field(default_factory=list)
    knowledge_documents: list[KnowledgeDocument] = Field(default_factory=list)


class OperationalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window: ReportWindow
    period_start: datetime
    period_end: datetime
    metrics: OperationalMetrics
    recommendations: list[ImprovementSuggestion] = Field(default_factory=list)


class AnalystFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyst_name: str
    target: str
    verdict: FeedbackVerdict = FeedbackVerdict.REVISE
    comment: str
    tags: list[str] = Field(default_factory=list)


class FeedbackLoopResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    total_feedback: int
    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)
    summary: str


class ReportingService:
    def __init__(
        self,
        now_provider: Callable[[], datetime] | None = None,
        ticket_lifecycle: TicketLifecycleService | None = None,
    ) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._ticket_lifecycle = ticket_lifecycle or TicketLifecycleService(now_provider=self._now_provider)

    def generate_report(self, request: OperationalReportRequest) -> OperationalReport:
        as_of = request.as_of or self._now_provider()
        period_start = self._period_start(as_of, request.window)
        metrics = self._metrics(request.tickets, request.knowledge_documents, as_of)
        recommendations = self._recommendations(metrics)

        return OperationalReport(
            window=request.window,
            period_start=period_start,
            period_end=as_of,
            metrics=metrics,
            recommendations=recommendations,
        )

    def _metrics(
        self,
        tickets: list[Ticket],
        knowledge_documents: list[KnowledgeDocument],
        as_of: datetime,
    ) -> OperationalMetrics:
        assessments = [self._ticket_lifecycle.assess(ticket, as_of=as_of) for ticket in tickets]

        state_counts = Counter(ticket.state for ticket in tickets)
        elapsed_values = [assessment.elapsed_minutes for assessment in assessments if assessment.elapsed_minutes is not None]
        remaining_values = [assessment.remaining_minutes for assessment in assessments if assessment.remaining_minutes is not None]

        total_tickets = len(tickets)
        sla_at_risk_tickets = sum(1 for assessment in assessments if assessment.risk_level.value in {"watch", "high", "critical"})
        sla_breaches = sum(1 for assessment in assessments if assessment.risk_level.value == "critical")

        return OperationalMetrics(
            total_tickets=total_tickets,
            open_tickets=state_counts[TicketState.NEW] + state_counts[TicketState.OPEN],
            pending_tickets=state_counts[TicketState.PENDING],
            closed_tickets=state_counts[TicketState.CLOSED],
            merged_tickets=state_counts[TicketState.MERGED],
            backlog_tickets=state_counts[TicketState.NEW] + state_counts[TicketState.OPEN] + state_counts[TicketState.PENDING],
            paused_tickets=sum(1 for assessment in assessments if assessment.lifecycle_state.value == "paused"),
            sla_assessed_tickets=sum(1 for assessment in assessments if assessment.solution_time_minutes is not None),
            sla_at_risk_tickets=sla_at_risk_tickets,
            sla_breaches=sla_breaches,
            average_elapsed_minutes=round(mean(elapsed_values), 2) if elapsed_values else 0.0,
            average_remaining_minutes=round(mean(remaining_values), 2) if remaining_values else 0.0,
            sla_compliance_rate=round((total_tickets - sla_breaches) / total_tickets, 4) if total_tickets else 0.0,
            knowledge_documents=len(knowledge_documents),
        )

    def _recommendations(self, metrics: OperationalMetrics) -> list[ImprovementSuggestion]:
        if metrics.total_tickets == 0:
            return []

        recommendations: list[ImprovementSuggestion] = []

        if metrics.sla_breaches > 0:
            recommendations.append(
                ImprovementSuggestion(
                    kind="runbook",
                    title="Create SLA breach runbook",
                    reason="Tickets already crossed the SLA line, so analysts need a deterministic breach playbook.",
                    source="operational_report",
                    priority="high",
                    placeholder="Document the first response, escalation path, and customer update template.",
                    evidence={"sla_breaches": metrics.sla_breaches},
                )
            )

        if metrics.backlog_tickets > metrics.closed_tickets:
            recommendations.append(
                ImprovementSuggestion(
                    kind="rule",
                    title="Tighten backlog routing rules",
                    reason="Backlog is larger than the resolved flow, so the triage rules need a stricter handoff.",
                    source="operational_report",
                    priority="medium",
                    placeholder="Refine queue rules for high-volume or aging tickets.",
                    evidence={"backlog_tickets": metrics.backlog_tickets, "closed_tickets": metrics.closed_tickets},
                )
            )

        if metrics.pending_tickets > 0:
            recommendations.append(
                ImprovementSuggestion(
                    kind="prompt_placeholder",
                    title="Add a pending follow-up prompt placeholder",
                    reason="Pending tickets indicate the analyst needs a reusable follow-up template.",
                    source="operational_report",
                    priority="medium",
                    placeholder="Ask for the missing detail, next action, and expected response time.",
                    evidence={"pending_tickets": metrics.pending_tickets},
                )
            )

        if metrics.knowledge_documents == 0:
            recommendations.append(
                ImprovementSuggestion(
                    kind="runbook",
                    title="Seed the knowledge baseline",
                    reason="No knowledge documents were provided, so repeat issues cannot be operationalized yet.",
                    source="operational_report",
                    priority="medium",
                    placeholder="Capture a short runbook for the recurring ticket pattern.",
                    evidence={"knowledge_documents": metrics.knowledge_documents},
                )
            )

        return self._unique_suggestions(recommendations)

    @staticmethod
    def _unique_suggestions(items: list[ImprovementSuggestion]) -> list[ImprovementSuggestion]:
        unique: list[ImprovementSuggestion] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.kind, item.title)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _period_start(as_of: datetime, window: ReportWindow) -> datetime:
        delta = timedelta(days=1 if window is ReportWindow.DAILY else 7)
        return as_of - delta


class FeedbackLoopService:
    def __init__(self) -> None:
        self._feedback: list[FeedbackLoopResponse] = []

    def record_feedback(self, request: AnalystFeedbackRequest) -> FeedbackLoopResponse:
        suggestions = self._suggestions_from_feedback(request)
        response = FeedbackLoopResponse(
            feedback_id=str(uuid4()),
            total_feedback=len(self._feedback) + 1,
            suggestions=suggestions,
            summary=self._summary(request, suggestions),
        )
        self._feedback.append(response)
        return response

    def list_feedback(self) -> list[FeedbackLoopResponse]:
        return list(self._feedback)

    def _suggestions_from_feedback(self, request: AnalystFeedbackRequest) -> list[ImprovementSuggestion]:
        text = " ".join([request.target, request.comment, " ".join(request.tags)]).lower()
        suggestions: list[ImprovementSuggestion] = []

        if any(term in text for term in ("wrong queue", "misroute", "routing", "route")):
            suggestions.append(
                ImprovementSuggestion(
                    kind="rule",
                    title="Adjust queue routing rule",
                    reason="The analyst reported a misroute, so the queue rule should be tightened.",
                    source="feedback",
                    priority="high" if request.verdict is FeedbackVerdict.REJECT else "medium",
                    placeholder="Refine the triage condition that selected the wrong queue.",
                    evidence={"target": request.target, "verdict": request.verdict.value},
                )
            )

        if any(term in text for term in ("verbose", "too long", "lengthy", "long")):
            suggestions.append(
                ImprovementSuggestion(
                    kind="prompt_placeholder",
                    title="Shorten the copilot response prompt",
                    reason="The analyst asked for a tighter answer, so the prompt should be compressed.",
                    source="feedback",
                    priority="medium",
                    placeholder="Answer in 3 bullet points and stop when the analyst has enough context.",
                    evidence={"target": request.target},
                )
            )

        if any(term in text for term in ("runbook", "knowledge article", "knowledge", "article", "playbook")):
            suggestions.append(
                ImprovementSuggestion(
                    kind="runbook",
                    title="Update the runbook or knowledge article",
                    reason="The feedback explicitly points to missing operational knowledge.",
                    source="feedback",
                    priority="high" if request.verdict is FeedbackVerdict.REJECT else "medium",
                    placeholder="Add the missing resolution steps and the escalation criteria.",
                    evidence={"target": request.target, "tags": request.tags},
                )
            )

        if not suggestions:
            suggestions.append(
                ImprovementSuggestion(
                    kind="prompt_placeholder",
                    title="Capture a reusable prompt placeholder",
                    reason="No explicit rule or runbook gap was detected, so the safest next step is to preserve the analyst wording.",
                    source="feedback",
                    priority="low",
                    placeholder=request.comment,
                    evidence={"target": request.target, "verdict": request.verdict.value},
                )
            )

        return ReportingService._unique_suggestions(suggestions)

    @staticmethod
    def _summary(request: AnalystFeedbackRequest, suggestions: list[ImprovementSuggestion]) -> str:
        suggestion_count = len(suggestions)
        noun = "suggestion" if suggestion_count == 1 else "suggestions"
        return f"Recorded {request.verdict.value} feedback for {request.target} with {suggestion_count} improvement {noun}."
