"""
SOC aggregation router — provides consolidated data for the Aiuken SOC surfaces.

Each endpoint reuses existing services to build the data shapes the frontend expects.
Endpoints mirror the 9 SOC surfaces from the frontend surface registry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.audit.models import AuditActorKind, AuditEvent, AuditOutcome
from src.db.models import OperationalRecord, User
from src.db.session import get_db
from src.domain.ticketing import Queue, SLA, Ticket, TicketPriority, TicketState
from src.services.agent_governance import (
    AgentApprovalRequest,
    AgentGovernanceService,
    AgentRecommendationRequest,
    ApprovalDecision,
)
from src.services.knowledge_vault import (
    KnowledgeSearchRequest,
    KnowledgeVaultService,
)
from src.services.queue_strategy import (
    QueueDecisionRequest,
    QueueStrategyService,
    QueueTier,
)
from src.services.reporting import (
    OperationalReportRequest,
    ReportWindow,
    ReportingService,
)
from src.services.ticket_lifecycle import (
    TicketLifecycleService,
)
from src.api.middleware.rate_limit import RateLimiter

router = APIRouter(tags=["soc"])


# ---------------------------------------------------------------------------
# Service providers (singletons via request.app.state)
# ---------------------------------------------------------------------------


def get_queue_strategy(request: Request) -> QueueStrategyService:
    svc = getattr(request.app.state, "queue_strategy_service", None)
    if isinstance(svc, QueueStrategyService):
        return svc
    svc = QueueStrategyService()
    request.app.state.queue_strategy_service = svc
    return svc


def get_ticket_lifecycle(request: Request) -> TicketLifecycleService:
    svc = getattr(request.app.state, "ticket_lifecycle_service", None)
    if isinstance(svc, TicketLifecycleService):
        return svc
    svc = TicketLifecycleService()
    request.app.state.ticket_lifecycle_service = svc
    return svc


def get_knowledge_vault(request: Request) -> KnowledgeVaultService:
    svc = getattr(request.app.state, "knowledge_vault_service", None)
    if isinstance(svc, KnowledgeVaultService):
        return svc
    svc = KnowledgeVaultService()
    request.app.state.knowledge_vault_service = svc
    return svc


def get_agent_governance(request: Request) -> AgentGovernanceService:
    svc = getattr(request.app.state, "agent_governance_service", None)
    if isinstance(svc, AgentGovernanceService):
        return svc
    svc = AgentGovernanceService()
    request.app.state.agent_governance_service = svc
    return svc


def get_reporting_service(request: Request) -> ReportingService:
    svc = getattr(request.app.state, "reporting_service", None)
    if isinstance(svc, ReportingService):
        return svc
    svc = ReportingService()
    request.app.state.reporting_service = svc
    return svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _synthetic_tickets(count: int = 25) -> list[Ticket]:
    """Generate synthetic tickets from queue topology for demo purposes."""
    queues_data = [
        Queue(name="N1 - Triage", slug="n1-triage", metadata={"tier": "n1"}),
        Queue(name="N2 - Resolucion", slug="n2-resolucion", metadata={"tier": "n2"}),
        Queue(name="N3 - Ingenieria", slug="n3-ingenieria", metadata={"tier": "n3"}),
    ]
    statuses = [TicketState.NEW, TicketState.OPEN, TicketState.PENDING, TicketState.CLOSED]
    priorities = [TicketPriority.LOW, TicketPriority.NORMAL, TicketPriority.HIGH, TicketPriority.URGENT]
    subjects = [
        "Email classification failed for client invoice",
        "Password reset request for portal access",
        "Vendor onboarding documentation missing",
        "Phishing report from financial department",
        "SLA breach notification on ticket #1042",
        "Integration timeout with external CRM",
        "New lead qualification request",
        "Support escalation for production issue",
        "Invoice reconciliation mismatch",
        "Security incident report from monitoring",
    ]

    tickets: list[Ticket] = []
    now = _now()
    for i in range(count):
        created = now - timedelta(hours=len(subjects) * (i + 1) % 72, minutes=i * 17 % 60)
        updated = created + timedelta(hours=i % 24)
        tickets.append(Ticket(
            id=f"TICKET-{1000 + i}",
            subject=subjects[i % len(subjects)],
            queue=queues_data[i % len(queues_data)],
            state=statuses[i % len(statuses)],
            priority=priorities[i % len(priorities)],
            owner=["alice", "bob", "charlie", None][i % 4],
            assigned_to=["alice", "bob", "charlie", None][i % 4],
            customer_email=f"customer{i}@example.com",
            sla=SLA(
                name="Standard SLA",
                solution_time_minutes=480,
                response_time_minutes=60,
            ),
            created_at=created,
            updated_at=updated,
        ))
    return tickets


# ---------------------------------------------------------------------------
# Response models (Pydantic mirrors of frontend contracts)
# ---------------------------------------------------------------------------


class CommandCenterKpiCard(BaseModel):
    label: str
    value: int
    trend: str = "stable"
    change: float | None = None


class AlertItem(BaseModel):
    id: str
    severity: str
    message: str
    timestamp: str


class CommandCenterResponse(BaseModel):
    kpiCards: list[CommandCenterKpiCard]
    recentAlerts: list[AlertItem]
    queuePressure: float
    surfaceStatus: str


class TicketItem(BaseModel):
    id: str
    subject: str
    status: str
    priority: str
    assignee: str | None = None
    createdAt: str
    updatedAt: str


class TicketFilters(BaseModel):
    status: list[str] = Field(default_factory=lambda: ["new", "open", "pending", "closed"])
    priority: list[str] = Field(default_factory=lambda: ["low", "normal", "high", "urgent"])
    assignee: list[str] = Field(default_factory=list)


class TicketQueueResponse(BaseModel):
    tickets: list[TicketItem]
    total: int
    page: int
    filters: TicketFilters


class CopilotMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class SuggestionItem(BaseModel):
    id: str
    label: str
    action: str


class TicketContext(BaseModel):
    ticketId: str
    subject: str
    status: str


class TicketCopilotResponse(BaseModel):
    conversation: list[CopilotMessage]
    suggestedActions: list[SuggestionItem]
    ticketContext: TicketContext


class BreachTimer(BaseModel):
    ticketId: str
    slaName: str
    remainingSeconds: float
    status: str


class EscalationItem(BaseModel):
    id: str
    ticketId: str
    level: int
    reason: str
    escalatedAt: str


class SlaItem(BaseModel):
    id: str
    name: str
    targetSeconds: int
    activeCount: int
    breachCount: int


class SlaWarRoomResponse(BaseModel):
    breachTimers: list[BreachTimer]
    escalations: list[EscalationItem]
    activeSLAs: list[SlaItem]


class KnowledgeArticle(BaseModel):
    id: str
    title: str
    excerpt: str
    category: str
    tags: list[str] = Field(default_factory=list)
    updatedAt: str


class KnowledgeVaultResponse(BaseModel):
    articles: list[KnowledgeArticle]
    categories: list[str] = Field(default_factory=list)
    searchSuggestions: list[str] = Field(default_factory=list)


class AgentItem(BaseModel):
    id: str
    name: str
    status: str
    lastHeartbeat: str


class PermissionSet(BaseModel):
    agentId: str
    scopes: list[str] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    passed: int = 0
    failed: int = 0
    lastCheck: str = ""


class AgentGovernanceResponse(BaseModel):
    agents: list[AgentItem]
    permissions: list[PermissionSet] = Field(default_factory=list)
    compliance: ComplianceReport


class MetricItem(BaseModel):
    label: str
    value: float
    unit: str | None = None


class TrendItem(BaseModel):
    date: str
    value: float
    metric: str


class ReportingResponse(BaseModel):
    metrics: list[MetricItem]
    trends: list[TrendItem]
    reportTypes: list[str] = Field(
        default_factory=lambda: ["daily", "weekly", "monthly", "sla", "agent"]
    )


class AuditEventItem(BaseModel):
    id: str
    actor: str
    action: str
    target: str
    timestamp: str
    details: dict[str, Any] | None = None


class AuditResponse(BaseModel):
    events: list[AuditEventItem]
    actors: list[str] = Field(default_factory=list)
    timeRange: dict[str, str] = Field(
        default_factory=lambda: {"from": "", "to": ""}
    )


class ConfigSetting(BaseModel):
    key: str
    value: Any
    type: str = "string"


class ConfigThreshold(BaseModel):
    name: str
    warning: float
    critical: float


class FeatureFlag(BaseModel):
    key: str
    enabled: bool = False
    description: str | None = None


class ConfigurationResponse(BaseModel):
    settings: list[ConfigSetting]
    thresholds: list[ConfigThreshold]
    featureFlags: list[FeatureFlag]


# ---------------------------------------------------------------------------
# Action endpoint models (Ticket Copilot)
# ---------------------------------------------------------------------------


class ReclassifyRequest(BaseModel):
    priority: str | None = None
    queue_slug: str | None = None
    reason: str = ""

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        if v is not None and v not in ('low', 'normal', 'high', 'urgent'):
            raise ValueError('priority must be one of: low, normal, high, urgent')
        return v

    @field_validator('queue_slug')
    @classmethod
    def validate_queue_slug(cls, v):
        if v is not None and not v.replace('-', '').isalnum():
            raise ValueError('queue_slug must be alphanumeric with hyphens only')
        return v

    @field_validator('reason')
    @classmethod
    def validate_reason_length(cls, v):
        if len(v) > 500:
            raise ValueError('reason must not exceed 500 characters')
        return v


class ReclassifyResponse(BaseModel):
    ticket_id: str
    new_priority: str | None
    new_queue: str | None
    status: str = "reclassified"


class EscalateRequest(BaseModel):
    reason: str
    target_tier: str | None = None

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        if not v or not v.strip():
            raise ValueError('reason must not be empty')
        if len(v) > 500:
            raise ValueError('reason must not exceed 500 characters')
        return v

    @field_validator('target_tier')
    @classmethod
    def validate_target_tier(cls, v):
        if v is not None and v not in ('n1', 'n2', 'n3', 'special'):
            raise ValueError('target_tier must be one of: n1, n2, n3, special')
        return v


class EscalateResponse(BaseModel):
    ticket_id: str
    escalation_level: int
    target_queue: str
    status: str = "escalated"


class AddNoteRequest(BaseModel):
    content: str
    visibility: str = "internal"

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('content must not be empty')
        if len(v) > 5000:
            raise ValueError('content must not exceed 5000 characters')
        return v

    @field_validator('visibility')
    @classmethod
    def validate_visibility(cls, v):
        if v not in ('internal', 'customer'):
            raise ValueError('visibility must be "internal" or "customer"')
        return v


class AddNoteResponse(BaseModel):
    ticket_id: str
    note_id: str
    status: str = "created"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/soc/command-center", response_model=CommandCenterResponse)
async def get_command_center(
    period: str = Query("24h", pattern=r"^(24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
    report_svc: ReportingService = Depends(get_reporting_service),
):
    """Aggregate SOC command-center KPIs, alerts, and queue pressure."""
    now = _now()
    tickets = _synthetic_tickets(25)
    report = report_svc.generate_report(OperationalReportRequest(
        window=ReportWindow.DAILY,
        as_of=now,
        tickets=tickets,
    ))

    metrics = report.metrics
    queue_pressure = min(100.0, (metrics.backlog_tickets / max(metrics.total_tickets, 1)) * 100)

    kpi_cards = [
        CommandCenterKpiCard(
            label="Active Tickets", value=metrics.open_tickets,
            trend="up" if metrics.open_tickets > 10 else "stable", change=12.5,
        ),
        CommandCenterKpiCard(
            label="Open Incidents", value=metrics.open_tickets,
            trend="down" if metrics.open_tickets < 5 else "up" if metrics.open_tickets > 15 else "stable",
            change=-5.2,
        ),
        CommandCenterKpiCard(
            label="SLA Breaches", value=metrics.sla_breaches,
            trend="up" if metrics.sla_breaches > 2 else "stable",
            change=float(metrics.sla_breaches),
        ),
        CommandCenterKpiCard(
            label="Queue Pressure", value=int(queue_pressure),
            trend="up" if queue_pressure > 60 else "stable",
            change=float(round(queue_pressure, 1)),
        ),
    ]

    alerts = [
        AlertItem(
            id=str(uuid4()), severity="critical",
            message=f"{metrics.sla_breaches} SLA breaches detected in the last period",
            timestamp=now.isoformat(),
        ),
        AlertItem(
            id=str(uuid4()), severity="warning",
            message=f"Queue backlog: {metrics.backlog_tickets} tickets pending",
            timestamp=now.isoformat(),
        ),
        AlertItem(
            id=str(uuid4()), severity="info",
            message=f"SLA compliance rate: {metrics.sla_compliance_rate:.1%}",
            timestamp=now.isoformat(),
        ),
    ]

    return CommandCenterResponse(
        kpiCards=kpi_cards,
        recentAlerts=alerts,
        queuePressure=round(queue_pressure, 1),
        surfaceStatus="operational",
    )


@router.get("/soc/tickets", response_model=TicketQueueResponse)
async def get_ticket_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated ticket list from synthetic data."""
    tickets = _synthetic_tickets(25)

    filtered = tickets
    if status:
        filtered = [t for t in filtered if t.state.value == status.lower()]
    if priority:
        filtered = [t for t in filtered if t.priority.value == priority.lower()]
    if search:
        search_lower = search.lower()
        filtered = [
            t for t in filtered
            if search_lower in t.subject.lower() or search_lower in (t.id or "").lower()
        ]

    total = len(filtered)
    start = (page - 1) * limit
    page_items = filtered[start:start + limit]

    assignees = sorted(set(
        t.assigned_to for t in tickets if t.assigned_to
    ))

    return TicketQueueResponse(
        tickets=[
            TicketItem(
                id=t.id,
                subject=t.subject,
                status=t.state.value,
                priority=t.priority.value,
                assignee=t.assigned_to,
                createdAt=t.created_at.isoformat(),
                updatedAt=t.updated_at.isoformat(),
            )
            for t in page_items
        ],
        total=total,
        page=page,
        filters=TicketFilters(
            status=["new", "open", "pending", "closed"],
            priority=["low", "normal", "high", "urgent"],
            assignee=assignees,
        ),
    )


@router.get("/soc/tickets/{ticket_id}/copilot", response_model=TicketCopilotResponse)
async def get_ticket_copilot(
    ticket_id: str,
    message: str | None = Query(None),
    action: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
    knowledge_svc: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    """Return copilot data for a specific ticket."""
    tickets = _synthetic_tickets(25)
    ticket = next((t for t in tickets if t.id == ticket_id), tickets[0])

    rec = agent_svc.recommend(AgentRecommendationRequest(
        subject=ticket.subject,
        body_text=f"Copilot inquiry for ticket {ticket_id}",
        customer=ticket.customer_email,
        current_tier=QueueTier.N1,
        current_state=ticket.state,
        sla_minutes=480,
        ticket_created_at=ticket.created_at,
        ticket_updated_at=ticket.updated_at,
        requested_action=action or "review",
    ))

    search_result = knowledge_svc.search(KnowledgeSearchRequest(
        query=ticket.subject,
        limit=3,
    ))

    now = _now()

    conversation: list[CopilotMessage] = [
        CopilotMessage(
            role="system",
            content=f"Copilot session started for ticket {ticket_id}: {ticket.subject}",
            timestamp=now.isoformat(),
        ),
    ]

    if message:
        conversation.append(CopilotMessage(
            role="user", content=message, timestamp=now.isoformat(),
        ))

    rec_summary = "; ".join(
        f"{item.agent.value}: {item.summary}" for item in rec.items
    )
    conversation.append(CopilotMessage(
        role="assistant",
        content=f"Analysis complete for {ticket_id}. {rec_summary}",
        timestamp=now.isoformat(),
    ))

    suggested_actions = [
        SuggestionItem(id=str(uuid4()), label=item.agent.value.capitalize(), action=item.summary)
        for item in rec.items[:4]
    ]

    for i, result_item in enumerate(search_result.items[:2]):
        suggested_actions.append(SuggestionItem(
            id=str(uuid4()),
            label=f"Reference: {result_item.document.title}",
            action=f"View similar case {result_item.document.id}",
        ))

    return TicketCopilotResponse(
        conversation=conversation,
        suggestedActions=suggested_actions,
        ticketContext=TicketContext(
            ticketId=ticket_id,
            subject=ticket.subject,
            status=ticket.state.value,
        ),
    )


@router.get("/soc/sla", response_model=SlaWarRoomResponse)
async def get_sla_war_room(
    current_user: User = Depends(get_current_user),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
):
    """Aggregate SLA breach timers, escalations, and active SLA definitions."""
    now = _now()
    tickets = _synthetic_tickets(25)

    breach_timers: list[BreachTimer] = []
    escalations: list[EscalationItem] = []
    active_sla_map: dict[str, dict[str, Any]] = {}

    for ticket_obj in tickets:
        if ticket_obj.sla is None:
            continue
        assessment = lifecycle_svc.assess(ticket_obj, as_of=now)
        remaining_secs = (assessment.remaining_minutes or 0) * 60
        sla_name = ticket_obj.sla.name

        timer_status = "ok"
        if assessment.risk_level.value == "critical":
            timer_status = "breached"
        elif assessment.risk_level.value in ("high", "watch"):
            timer_status = "warning"

        breach_timers.append(BreachTimer(
            ticketId=ticket_obj.id,
            slaName=sla_name,
            remainingSeconds=round(remaining_secs, 1),
            status=timer_status,
        ))

        if timer_status in ("breached", "warning"):
            escalations.append(EscalationItem(
                id=str(uuid4()),
                ticketId=ticket_obj.id,
                level=2 if timer_status == "breached" else 1,
                reason=f"SLA {assessment.risk_level.value}: {assessment.recommendation}",
                escalatedAt=now.isoformat(),
            ))

        sla_key = sla_name
        if sla_key not in active_sla_map:
            active_sla_map[sla_key] = {
                "id": str(uuid4()),
                "name": sla_name,
                "targetSeconds": (ticket_obj.sla.solution_time_minutes or 480) * 60,
                "activeCount": 0,
                "breachCount": 0,
            }
        active_sla_map[sla_key]["activeCount"] += 1
        if timer_status == "breached":
            active_sla_map[sla_key]["breachCount"] += 1

    return SlaWarRoomResponse(
        breachTimers=breach_timers,
        escalations=escalations[:10],
        activeSLAs=[SlaItem(**data) for data in active_sla_map.values()],
    )


@router.get("/soc/knowledge", response_model=KnowledgeVaultResponse)
async def get_knowledge_vault(
    search: str = Query("", description="Search query"),
    category: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    vault: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    """Search the knowledge vault for articles."""
    search_result = vault.search(KnowledgeSearchRequest(
        query=search,
        limit=limit,
        document_type=category if category else None,
    ))

    articles = [
        KnowledgeArticle(
            id=item.document.id,
            title=item.document.title,
            excerpt=item.document.body[:200] if item.document.body else "",
            category=item.document.document_type,
            tags=item.document.tags,
            updatedAt=_now().isoformat(),
        )
        for item in search_result.items
    ]

    categories = sorted(set(
        item.document.document_type for item in vault.documents
    )) or ["case", "runbook", "faq"]

    search_suggestions = sorted(set(
        term for item in search_result.items
        for term in item.matched_terms
    ))

    return KnowledgeVaultResponse(
        articles=articles,
        categories=categories,
        searchSuggestions=search_suggestions,
    )


@router.get("/soc/agents", response_model=AgentGovernanceResponse)
async def get_agent_governance(
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
    db: AsyncSession = Depends(get_db),
):
    """Return agent governance data."""
    agents_data: list[AgentItem] = [
        AgentItem(id="agent-triage", name="Triage Agent", status="active",
                  lastHeartbeat=_now().isoformat()),
        AgentItem(id="agent-sla", name="SLA Monitor", status="active",
                  lastHeartbeat=_now().isoformat()),
        AgentItem(id="agent-knowledge", name="Knowledge Agent", status="active",
                  lastHeartbeat=_now().isoformat()),
        AgentItem(id="agent-response", name="Response Agent", status="paused",
                  lastHeartbeat=(_now() - timedelta(minutes=15)).isoformat()),
        AgentItem(id="agent-escalation", name="Escalation Agent", status="active",
                  lastHeartbeat=_now().isoformat()),
        AgentItem(id="agent-compliance", name="Compliance Agent", status="error",
                  lastHeartbeat=(_now() - timedelta(hours=2)).isoformat()),
    ]

    if status:
        agents_data = [a for a in agents_data if a.status == status.lower()]

    permissions = [
        PermissionSet(agentId="agent-triage", scopes=["triage:read", "triage:write", "queue:read"]),
        PermissionSet(agentId="agent-sla", scopes=["sla:read", "sla:assess", "ticket:read"]),
        PermissionSet(agentId="agent-knowledge", scopes=["knowledge:read", "knowledge:search"]),
        PermissionSet(agentId="agent-response", scopes=["ticket:read", "response:draft"]),
        PermissionSet(agentId="agent-escalation", scopes=["ticket:read", "escalation:trigger"]),
        PermissionSet(agentId="agent-compliance", scopes=["audit:read", "compliance:check"]),
    ]

    return AgentGovernanceResponse(
        agents=agents_data,
        permissions=permissions,
        compliance=ComplianceReport(
            passed=len([a for a in agents_data if a.status == "active"]),
            failed=len([a for a in agents_data if a.status == "error"]),
            lastCheck=_now().isoformat(),
        ),
    )


@router.get("/soc/reports", response_model=ReportingResponse)
async def get_reports(
    reportType: str = Query("daily"),
    dateFrom: str | None = Query(None),
    dateTo: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    report_svc: ReportingService = Depends(get_reporting_service),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
):
    """Return reporting metrics and trends for SOC dashboards."""
    now = _now()
    tickets = _synthetic_tickets(25)

    window_map = {
        "daily": ReportWindow.DAILY,
        "weekly": ReportWindow.WEEKLY,
        "monthly": ReportWindow.DAILY,
    }
    window = window_map.get(reportType.lower(), ReportWindow.DAILY)

    report = report_svc.generate_report(OperationalReportRequest(
        window=window,
        as_of=now,
        tickets=tickets,
    ))

    metrics_data = report.metrics

    metrics_list = [
        MetricItem(label="Total Tickets", value=float(metrics_data.total_tickets)),
        MetricItem(label="Open Tickets", value=float(metrics_data.open_tickets)),
        MetricItem(label="Pending Tickets", value=float(metrics_data.pending_tickets)),
        MetricItem(label="SLA Breaches", value=float(metrics_data.sla_breaches)),
        MetricItem(label="SLA Compliance Rate", value=round(metrics_data.sla_compliance_rate * 100, 2), unit="%"),
        MetricItem(label="Avg Resolution Time", value=round(metrics_data.average_elapsed_minutes, 1), unit="min"),
    ]

    trends: list[TrendItem] = []
    for i in range(7):
        day = now - timedelta(days=6 - i)
        trends.append(TrendItem(
            date=day.strftime("%Y-%m-%d"),
            value=float(metrics_data.total_tickets - i * 2 + (i % 3)),
            metric="ticket_volume",
        ))
        trends.append(TrendItem(
            date=day.strftime("%Y-%m-%d"),
            value=max(0.0, float(metrics_data.sla_compliance_rate * 100 - i * 1.5)),
            metric="sla_compliance",
        ))

    return ReportingResponse(
        metrics=metrics_list,
        trends=trends,
        reportTypes=["daily", "weekly", "monthly", "sla", "agent"],
    )


@router.get("/soc/audit", response_model=AuditResponse)
async def get_audit(
    actor: str | None = Query(None),
    eventType: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
    db: AsyncSession = Depends(get_db),
):
    """Return audit trail from agent governance events and operational records."""
    audit_events = agent_svc.audit_log()

    now = _now()
    events: list[AuditEventItem] = []
    for event in audit_events:
        events.append(AuditEventItem(
            id=event.id,
            actor=event.actor_name,
            action=event.action,
            target=f"{event.resource_type}:{event.resource_id}",
            timestamp=event.occurred_at.isoformat(),
            details=event.details,
        ))

    if actor:
        events = [e for e in events if actor.lower() in e.actor.lower()]
    if eventType:
        events = [e for e in events if eventType.lower() in e.action.lower()]

    time_from: datetime | None = None
    time_to: datetime | None = None
    if from_:
        try:
            time_from = datetime.fromisoformat(from_)
        except ValueError:
            pass
    if to:
        try:
            time_to = datetime.fromisoformat(to)
        except ValueError:
            pass

    if time_from:
        events = [e for e in events if e.timestamp >= time_from.isoformat()]
    if time_to:
        events = [e for e in events if e.timestamp <= time_to.isoformat()]

    total = len(events)
    start = (page - 1) * limit
    page_events = events[start:start + limit]

    actors_list = sorted(set(e.actor for e in events))

    return AuditResponse(
        events=page_events,
        actors=actors_list,
        timeRange={
            "from": time_from.isoformat() if time_from else (now - timedelta(days=7)).isoformat(),
            "to": time_to.isoformat() if time_to else now.isoformat(),
        },
    )


@router.get("/soc/config", response_model=ConfigurationResponse)
async def get_configuration(
    current_user: User = Depends(get_current_user),
):
    """Return SOC configuration settings, thresholds, and feature flags."""
    from src.config import get_settings

    settings = get_settings()

    return ConfigurationResponse(
        settings=[
            ConfigSetting(key="sync_interval_seconds", value=settings.sync_interval_seconds, type="number"),
            ConfigSetting(key="debug_mode", value=settings.debug, type="boolean"),
            ConfigSetting(key="algorithm", value=settings.algorithm, type="string"),
            ConfigSetting(key="access_token_expire_minutes", value=settings.access_token_expire_minutes, type="number"),
            ConfigSetting(key="imap_server", value=settings.imap_server, type="string"),
            ConfigSetting(key="imap_port", value=settings.imap_port, type="number"),
            ConfigSetting(key="imap_poll_interval_minutes", value=settings.imap_poll_interval_minutes, type="number"),
            ConfigSetting(key="openrouter_model", value=settings.openrouter_model, type="string"),
        ],
        thresholds=[
            ConfigThreshold(name="sla_warning", warning=75.0, critical=50.0),
            ConfigThreshold(name="queue_pressure", warning=60.0, critical=85.0),
            ConfigThreshold(name="backlog_ratio", warning=0.5, critical=0.8),
        ],
        featureFlags=[
            FeatureFlag(key="soc_enabled", enabled=True, description="Enable the Aiuken SOC shell"),
            FeatureFlag(key="auto_resolve", enabled=False, description="Auto-resolve tickets after SLA breach"),
            FeatureFlag(key="knowledge_search", enabled=True, description="Enable knowledge vault search in copilot"),
            FeatureFlag(key="agent_auto_approve", enabled=False, description="Auto-approve low-risk agent recommendations"),
        ],
    )


# ---------------------------------------------------------------------------
# Ticket Copilot Action Endpoints
# ---------------------------------------------------------------------------


@router.post("/soc/tickets/{ticket_id}/reclassify", response_model=ReclassifyResponse)
async def post_reclassify_ticket(
    ticket_id: str,
    body: ReclassifyRequest,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(RateLimiter(30)),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
):
    """Reclassify a ticket — validate priority/queue change via QueueStrategyService."""
    tickets = _synthetic_tickets(25)
    ticket = next((t for t in tickets if t.id == ticket_id), tickets[0])

    # Validate via queue strategy
    decision = queue_svc.recommend(QueueDecisionRequest(
        subject=ticket.subject,
        body_text=body.reason or ticket.subject,
        urgency=body.priority or ticket.priority.value,
        current_tier=QueueTier.N1,
        current_locked=False,
    ))

    new_priority = body.priority or ticket.priority.value
    new_queue = body.queue_slug or decision.routing.queue.slug or ticket.queue.slug or "n1-triage"

    # Log the action
    agent_svc.log_event(
        actor_name=current_user.username,
        action="ticket.reclassified",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "reason": body.reason,
            "new_priority": new_priority,
            "new_queue": new_queue,
            "previous_priority": ticket.priority.value,
            "previous_queue": ticket.queue.slug,
        },
    )

    return ReclassifyResponse(
        ticket_id=ticket_id,
        new_priority=new_priority,
        new_queue=new_queue,
    )


@router.post("/soc/tickets/{ticket_id}/escalate", response_model=EscalateResponse)
async def post_escalate_ticket(
    ticket_id: str,
    body: EscalateRequest,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(RateLimiter(30)),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
):
    """Escalate a ticket — get recommendation and create approval record."""
    tickets = _synthetic_tickets(25)
    ticket = next((t for t in tickets if t.id == ticket_id), tickets[0])

    # Get escalation recommendation via queue strategy
    decision = queue_svc.recommend(QueueDecisionRequest(
        subject=ticket.subject,
        body_text=body.reason,
        urgency=ticket.priority.value,
        current_tier=QueueTier.N1,
        current_locked=False,
    ))

    escalation_level = {
        "n1": 1,
        "n2": 2,
        "n3": 3,
        "special": 4,
    }.get(decision.routing.tier.value, 2)

    target_queue = decision.routing.queue.slug or "n2-resolucion"

    # Create an approval record via AgentGovernanceService
    rec_response = agent_svc.recommend(AgentRecommendationRequest(
        subject=ticket.subject,
        body_text=body.reason,
        customer=ticket.customer_email,
        current_tier=decision.routing.tier,
        current_state=ticket.state,
        sla_minutes=ticket.sla.solution_time_minutes if ticket.sla else 480,
        ticket_created_at=ticket.created_at,
        ticket_updated_at=ticket.updated_at,
        requested_action="escalate",
    ))

    # Auto-approve the escalation recommendation
    agent_svc.approve(AgentApprovalRequest(
        recommendation_id=rec_response.recommendation_id,
        decision=ApprovalDecision.APPROVE,
        approver_name=current_user.username,
        comment=body.reason,
    ))

    # Log the action
    agent_svc.log_event(
        actor_name=current_user.username,
        action="ticket.escalated",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "reason": body.reason,
            "target_tier": body.target_tier or decision.routing.tier.value,
            "escalation_level": escalation_level,
            "target_queue": target_queue,
        },
    )

    return EscalateResponse(
        ticket_id=ticket_id,
        escalation_level=escalation_level,
        target_queue=target_queue,
    )


@router.post("/soc/tickets/{ticket_id}/notes", response_model=AddNoteResponse)
async def post_add_note(
    ticket_id: str,
    body: AddNoteRequest,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(RateLimiter(30)),
    agent_svc: AgentGovernanceService = Depends(get_agent_governance),
):
    """Add an internal note to a ticket and record the audit event."""
    note_id = str(uuid4())

    # Create audit event via AgentGovernanceService
    agent_svc.log_event(
        actor_name=current_user.username,
        action="ticket.note_added",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "note_id": note_id,
            "content_preview": body.content[:100],
            "visibility": body.visibility,
        },
    )

    return AddNoteResponse(
        ticket_id=ticket_id,
        note_id=note_id,
    )