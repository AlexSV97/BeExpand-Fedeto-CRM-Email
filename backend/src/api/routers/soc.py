"""
SOC aggregation router — provides consolidated data for the Aiuken SOC surfaces.

Each endpoint reuses existing services to build the data shapes the frontend expects.
Endpoints mirror the 9 SOC surfaces from the frontend surface registry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.audit.models import AuditActorKind, AuditEvent, AuditOutcome
from src.db.models import OperationalRecord, User
from src.db.session import get_db
from src.domain.ticketing import ActorKind, Article, ArticleDraft, Queue, SLA, Ticket, TicketPriority, TicketState
from src.integrations.otrs_znuny import OtrsZnunyClient, OtrsZnunySettings
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
from src.services.escalation import EscalationRequest, EscalationService
from src.services.escalation_recording import (
    EscalationHistoryItem,
    EscalationHistoryResponse,
    EscalationRecordService,
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


async def get_knowledge_vault(request: Request) -> KnowledgeVaultService:
    svc = getattr(request.app.state, "knowledge_vault_service", None)
    if isinstance(svc, KnowledgeVaultService):
        return svc

    from src.llm_client import LLMClient
    from src.services.vector_store import VectorStore

    # Add seed documents if vault is empty
    documents = _seed_knowledge_documents()
    llm_client = LLMClient(use_chat_model=True)
    vector_store = VectorStore()

    svc = KnowledgeVaultService(
        documents=documents,
        vector_store=vector_store,
        llm_client=llm_client,
    )

    # Pre-embed all documents for RAG search
    await svc.embed_all_documents()

    request.app.state.knowledge_vault_service = svc
    return svc


def _seed_knowledge_documents() -> list[KnowledgeDocument]:
    """Return seed documents for the knowledge vault."""
    from src.services.knowledge_vault import KnowledgeDocument

    return [
        KnowledgeDocument(
            id="KB-001",
            title="Password Reset Procedure",
            body=(
                "Step-by-step guide for resetting user passwords in the OTRS portal. "
                "1. Verify user identity via security questions. "
                "2. Generate temporary password. "
                "3. Force password change on next login."
            ),
            document_type="case",
            tags=["password", "security", "authentication"],
        ),
        KnowledgeDocument(
            id="KB-002",
            title="SLA Breach Response Runbook",
            body=(
                "Standard operating procedure for SLA breach notifications. "
                "When SLA exceeds 90% of threshold, notify team lead. "
                "At 100%, escalate to N2 immediately."
            ),
            document_type="runbook",
            tags=["sla", "breach", "escalation", "urgent"],
        ),
        KnowledgeDocument(
            id="KB-003",
            title="VPN Access Troubleshooting",
            body=(
                "Common VPN connection issues and solutions. "
                "Check client version, verify credentials, test network connectivity, "
                "check firewall rules."
            ),
            document_type="faq",
            tags=["vpn", "network", "connectivity"],
        ),
        KnowledgeDocument(
            id="KB-004",
            title="Email Classification Guidelines",
            body=(
                "Rules for classifying incoming emails: "
                "SPAM (unsolicited bulk), PHISHING (suspicious links), "
                "SUPPORT (service requests), BILLING (invoice queries)."
            ),
            document_type="case",
            tags=["email", "classification", "security"],
        ),
        KnowledgeDocument(
            id="KB-005",
            title="Incident Response Plan",
            body=(
                "Tier 1: Acknowledge and categorize. "
                "Tier 2: Investigate and contain. "
                "Tier 3: Eradicate and recover. "
                "Post-incident: Document lessons learned."
            ),
            document_type="runbook",
            tags=["incident", "security", "response"],
        ),
        KnowledgeDocument(
            id="KB-006",
            title="New User Onboarding Checklist",
            body=(
                "Create account, assign mailbox, configure OTRS profile, "
                "set up VPN access, schedule security training, "
                "grant initial permissions."
            ),
            document_type="faq",
            tags=["onboarding", "user", "setup"],
        ),
    ]


def _get_agent_governance_service(request: Request) -> AgentGovernanceService:
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


CANONICAL_STATUS_OPTIONS = ["open", "in_progress", "pending", "resolved", "closed"]
CANONICAL_PRIORITY_OPTIONS = ["low", "medium", "high", "urgent", "critical"]

_STATUS_CANONICAL_MAP = {
    "new": "open",
    "open": "open",
    "in_progress": "in_progress",
    "pending": "pending",
    "resolved": "resolved",
    "closed": "closed",
    "merged": "closed",
}

_PRIORITY_CANONICAL_MAP = {
    "low": "low",
    "normal": "medium",
    "medium": "medium",
    "high": "high",
    "urgent": "urgent",
    "critical": "critical",
}

_PRIORITY_DOMAIN_MAP = {
    "low": TicketPriority.LOW,
    "medium": TicketPriority.MEDIUM,
    "high": TicketPriority.HIGH,
    "urgent": TicketPriority.URGENT,
    "critical": TicketPriority.CRITICAL,
}

_STATE_DOMAIN_MAP = {
    "open": TicketState.OPEN,
    "in_progress": TicketState.IN_PROGRESS,
    "pending": TicketState.PENDING,
    "resolved": TicketState.RESOLVED,
    "closed": TicketState.CLOSED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_status(value: str | None) -> str:
    raw = (value or "open").strip().lower()
    return _STATUS_CANONICAL_MAP.get(raw, "open")


def _canonical_priority(value: str | None) -> str:
    raw = (value or "medium").strip().lower()
    return _PRIORITY_CANONICAL_MAP.get(raw, "medium")


def _ticket_status(ticket: Ticket) -> str:
    return _canonical_status(ticket.state.value if ticket.state else None)


def _ticket_priority(ticket: Ticket) -> str:
    return _canonical_priority(ticket.priority.value if ticket.priority else None)


def _domain_priority(value: str | None) -> TicketPriority:
    return _PRIORITY_DOMAIN_MAP[_canonical_priority(value)]


def _domain_state(value: str | None) -> TicketState:
    return _STATE_DOMAIN_MAP[_canonical_status(value)]


def _queue_from_slug(slug: str | None) -> Queue | None:
    if not slug:
        return None
    label = slug.replace("-", " ").strip().title()
    return Queue(name=label, slug=slug)


def _synthetic_tickets(count: int = 25) -> list[Ticket]:
    """Generate synthetic tickets from queue topology for demo purposes."""
    queues_data = [
        Queue(name="N1 - Triage", slug="n1-triage", metadata={"tier": "n1"}),
        Queue(name="N2 - Resolucion", slug="n2-resolucion", metadata={"tier": "n2"}),
        Queue(name="N3 - Ingenieria", slug="n3-ingenieria", metadata={"tier": "n3"}),
    ]
    statuses = [TicketState.NEW, TicketState.OPEN, TicketState.PENDING, TicketState.CLOSED]
    priorities = [TicketPriority.LOW, TicketPriority.NORMAL, TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.URGENT, TicketPriority.CRITICAL]
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

    # Article content pools keyed by subject keyword
    _article_pool: dict[str, list[dict]] = {
        "classification": [
            {"title": "Classification error analysis", "body": "The email was flagged as SPAM by the auto-classifier but the client insists it is a valid invoice. Reviewing header metadata and DKIM signature.", "author": ActorKind.IA},
            {"title": "Manual reclassification performed", "body": "Reclassified the email from SPAM to BILLING. The invoice PDF is attached for reference. Flagging classifier rule for retraining.", "author": ActorKind.HUMAN},
            {"title": "Root cause identified", "body": "The classifier model was trained on outdated invoice templates. New template pattern added to the training set for next cycle.", "author": ActorKind.IA},
        ],
        "password": [
            {"title": "Verification steps completed", "body": "User identity verified via security questions. Temporary password generated and sent to registered alternate email.", "author": ActorKind.HUMAN},
            {"title": "Portal access restored", "body": "Password has been reset successfully. User confirmed access to the portal. Ticket can be resolved.", "author": ActorKind.HUMAN},
            {"title": "Audit log review", "body": "Reviewed access logs for the account. No unauthorized access detected. Password change was legitimate.", "author": ActorKind.IA},
        ],
        "onboarding": [
            {"title": "Missing documents identified", "body": "Vendor has not submitted tax ID certification or proof of insurance. Contacted vendor relations for follow-up.", "author": ActorKind.HUMAN},
            {"title": "Document request sent", "body": "Sent reminder to vendor with checklist of required documentation. Deadline set for 72 hours.", "author": ActorKind.IA},
            {"title": "Onboarding status update", "body": "Two of three documents received. Still awaiting signed MSA. Escalated to account manager.", "author": ActorKind.HUMAN},
        ],
        "phishing": [
            {"title": "Initial triage", "body": "Email reported by financial department contains suspicious link to 'fedeto-secure.com'. Domain registered 48 hours ago in Panama.", "author": ActorKind.IA},
            {"title": "Indicators of compromise", "body": "Extracted IOCs: sender IP 185.220.101.x, malicious URL, spoofed display name. Blocked at gateway level.", "author": ActorKind.IA},
            {"title": "User notified", "body": "Informed financial department that this is a confirmed phishing attempt. All users advised to be vigilant.", "author": ActorKind.HUMAN},
        ],
        "sla breach": [
            {"title": "SLA timer alert", "body": "Ticket has exceeded 90% of SLA solution time (432 of 480 minutes). Auto-escalation triggered to N2.", "author": ActorKind.IA},
            {"title": "Escalation initiated", "body": "Ticket escalated to N2 - Resolucion. Customer notified of expected delay. Priority bumped to HIGH.", "author": ActorKind.HUMAN},
            {"title": "Post-mortem analysis", "body": "Root cause: delayed response from third-party vendor. SLA process exception filed.", "author": ActorKind.IA},
        ],
        "integration": [
            {"title": "Connectivity test results", "body": "Ping to CRM endpoint timed out after 30 seconds. Certificate chain validated but TLS handshake fails intermittently.", "author": ActorKind.IA},
            {"title": "Workaround applied", "body": "Implemented retry logic with exponential backoff. Integration queue resumed processing with manual supervision.", "author": ActorKind.HUMAN},
            {"title": "Vendor ticket created", "body": "Opened support case with CRM vendor regarding API instability. Reference case CRM-88421.", "author": ActorKind.HUMAN},
        ],
        "lead qualification": [
            {"title": "Lead scoring complete", "body": "New lead scored at 82/100 based on firmographic and intent signals. Assigning to senior sales rep.", "author": ActorKind.IA},
            {"title": "Contact established", "body": "Spoke with prospect. Budget approved for Q3. Scheduling technical demo for next week.", "author": ActorKind.HUMAN},
            {"title": "Qualification summary", "body": "Lead meets all BANT criteria. Budget: confirmed. Authority: IT Director. Need: documented. Timeline: 30 days.", "author": ActorKind.HUMAN},
        ],
        "escalation": [
            {"title": "Incident severity assessment", "body": "Production issue affecting 200+ users. Critical path blocked. Declaring major incident per runbook.", "author": ActorKind.IA},
            {"title": "Bridge call initiated", "body": "War room established with Engineering, Support, and Infrastructure teams. ETA for fix: 2 hours.", "author": ActorKind.HUMAN},
            {"title": "Resolution deployed", "body": "Hotfix deployed to production. Monitoring confirms system stability. Post-incident review scheduled.", "author": ActorKind.HUMAN},
        ],
        "reconciliation": [
            {"title": "Discrepancy detected", "body": "Invoice #INV-4421 shows $12,480 but CRM record shows $11,950. Difference of $530 needs investigation.", "author": ActorKind.IA},
            {"title": "Billing audit results", "body": "Discrepancy traced to promo code not applied correctly. Credit memo issued for the difference.", "author": ActorKind.HUMAN},
            {"title": "Resolution confirmed", "body": "Customer confirmed receipt of adjusted invoice. Both systems now reconciled.", "author": ActorKind.HUMAN},
        ],
        "security incident": [
            {"title": "Alert verification", "body": "Monitoring system detected anomalous outbound traffic from workstation WS-442. Correlating with IDS alerts.", "author": ActorKind.IA},
            {"title": "Containment actions", "body": "Isolated affected workstation from network. Revoked API keys. Blocked suspicious outbound IPs at firewall.", "author": ActorKind.HUMAN},
            {"title": "Forensic analysis", "body": "Preliminary analysis indicates credential theft via phishing. No lateral movement detected. EDR sweep initiated.", "author": ActorKind.IA},
        ],
    }

    def _articles_for_ticket(subject: str, ticket_id: str, ticket_created: datetime, ticket_updated: datetime) -> list[Article]:
        """Generate 1-3 Article objects aligned to the ticket subject."""
        subject_lower = subject.lower()
        # Find the best matching pool key
        pool_key = next((k for k in _article_pool if k in subject_lower), None)
        pool = _article_pool.get(pool_key, _article_pool["classification"])
        # Pick 1-3 articles deterministically based on ticket number
        ticket_num = int(ticket_id.split("-")[-1])
        num_articles = (ticket_num % 3) + 1  # 1-3 articles
        articles: list[Article] = []
        pool_len = len(pool)
        for j in range(min(num_articles, pool_len)):
            entry = pool[j]
            # Stagger timestamps between created and updated
            ts = ticket_created + (ticket_updated - ticket_created) * (j + 1) / (pool_len + 1)
            articles.append(Article(
                id=f"ART-{ticket_num}-{j + 1}",
                ticket_id=ticket_id,
                author_kind=entry["author"],
                author_name=entry["author"].value.capitalize() if entry["author"] == ActorKind.IA else "Agent Support",
                subject=entry["title"],
                body_text=entry["body"],
                created_at=ts,
            ))
        return articles

    tickets: list[Ticket] = []
    now = _now()
    for i in range(count):
        created = now - timedelta(hours=len(subjects) * (i + 1) % 72, minutes=i * 17 % 60)
        updated = created + timedelta(hours=i % 24)
        ticket_id = f"TICKET-{1000 + i}"
        subject = subjects[i % len(subjects)]
        tickets.append(Ticket(
            id=ticket_id,
            subject=subject,
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
            articles=_articles_for_ticket(subject, ticket_id, created, updated),
            created_at=created,
            updated_at=updated,
        ))
    return tickets


# ---------------------------------------------------------------------------
# OTRS/Znuny Client Dependency
# ---------------------------------------------------------------------------


async def get_otrs_client(request: Request) -> OtrsZnunyClient | None:
    """Return a shared OTRS/Znuny client, or None if not configured."""
    client = getattr(request.app.state, "otrs_client", None)
    if client is not None:
        return client
    settings = OtrsZnunySettings()
    if settings.is_configured:
        client = OtrsZnunyClient(settings=settings)
        request.app.state.otrs_client = client
        return client
    return None  # Will trigger synthetic fallback


async def _resolve_tickets_with_mode(
    otrs: OtrsZnunyClient | None,
    count: int = 25,
) -> tuple[list[Ticket], str]:
    """Try OTRS first and return the operational mode used."""
    if otrs is not None:
        try:
            return await otrs.list_tickets(limit=count), "live"
        except Exception:
            return _synthetic_tickets(count), "degraded"
    return _synthetic_tickets(count), "demo"


async def _resolve_tickets(
    otrs: OtrsZnunyClient | None,
    count: int = 25,
) -> list[Ticket]:
    tickets, _mode = await _resolve_tickets_with_mode(otrs, count)
    return tickets


async def _resolve_ticket(
    otrs: OtrsZnunyClient | None,
    ticket_id: str,
) -> Ticket | None:
    """Try OTRS first, fall back to synthetic tickets."""
    if otrs is not None:
        try:
            return await otrs.get_ticket(ticket_id)
        except Exception:
            pass  # Fall through to synthetic
    tickets = _synthetic_tickets(25)
    return next((t for t in tickets if t.id == ticket_id), None)


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
    operatingMode: str = "demo"


class TicketItem(BaseModel):
    id: str
    subject: str
    status: str
    priority: str
    assignee: str | None = None
    createdAt: str
    updatedAt: str


class TicketFilters(BaseModel):
    status: list[str] = Field(default_factory=lambda: ["new", "open", "in_progress", "pending", "resolved", "closed", "merged"])
    priority: list[str] = Field(default_factory=lambda: ["low", "medium", "high", "urgent", "critical"])
    assignee: list[str] = Field(default_factory=list)


class TicketQueueResponse(BaseModel):
    tickets: list[TicketItem]
    total: int
    page: int
    filters: TicketFilters
    operatingMode: str = "demo"


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
    priority: str
    queue: str | None = None
    assignee: str | None = None
    customerEmail: str | None = None
    slaName: str | None = None
    articleCount: int = 0


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
    operatingMode: str = "demo"


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
    operatingMode: str = "demo"


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
        if v is not None and v not in ('low', 'medium', 'high', 'urgent', 'critical'):
            raise ValueError('priority must be one of: low, medium, high, urgent, critical')
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
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
    report_svc: ReportingService = Depends(get_reporting_service),
):
    """Aggregate SOC command-center KPIs, alerts, and queue pressure."""
    now = _now()
    tickets, operating_mode = await _resolve_tickets_with_mode(otrs, 25)
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
        operatingMode=operating_mode,
    )


@router.get("/soc/tickets", response_model=TicketQueueResponse)
async def get_ticket_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated ticket list."""
    tickets, operating_mode = await _resolve_tickets_with_mode(otrs, 25)

    filtered = tickets
    if status:
        canonical_status = _canonical_status(status)
        filtered = [t for t in filtered if _ticket_status(t) == canonical_status]
    if priority:
        canonical_priority = _canonical_priority(priority)
        filtered = [t for t in filtered if _ticket_priority(t) == canonical_priority]
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
                status=_ticket_status(t),
                priority=_ticket_priority(t),
                assignee=t.assigned_to,
                createdAt=t.created_at.isoformat(),
                updatedAt=t.updated_at.isoformat(),
            )
            for t in page_items
        ],
        total=total,
        page=page,
        filters=TicketFilters(
            status=CANONICAL_STATUS_OPTIONS,
            priority=CANONICAL_PRIORITY_OPTIONS,
            assignee=assignees,
        ),
        operatingMode=operating_mode,
    )


@router.get("/soc/tickets/{ticket_id}/copilot", response_model=TicketCopilotResponse)
async def get_ticket_copilot(
    ticket_id: str,
    message: str | None = Query(None),
    action: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
    knowledge_svc: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    """Return copilot data for a specific ticket."""
    ticket = await _resolve_ticket(otrs, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

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

    search_result = await knowledge_svc.search_rag(KnowledgeSearchRequest(
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
            status=_ticket_status(ticket),
            priority=_ticket_priority(ticket),
            queue=ticket.queue.name if ticket.queue else None,
            assignee=ticket.assigned_to,
            customerEmail=ticket.customer_email,
            slaName=ticket.sla.name if ticket.sla else None,
            articleCount=len(ticket.articles),
        ),
    )


@router.get("/soc/sla", response_model=SlaWarRoomResponse)
async def get_sla_war_room(
    current_user: User = Depends(get_current_user),
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
):
    """Aggregate SLA breach timers, escalations, and active SLA definitions."""
    now = _now()
    tickets, operating_mode = await _resolve_tickets_with_mode(otrs, 25)

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
        operatingMode=operating_mode,
    )


@router.get("/soc/knowledge", response_model=KnowledgeVaultResponse)
async def get_knowledge_vault(
    search: str = Query("", description="Search query"),
    category: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    vault: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    """Search the knowledge vault using hybrid RAG (keyword + semantic)."""
    search_result = await vault.search_rag(
        KnowledgeSearchRequest(
            query=search,
            limit=limit,
            document_type=category if category else None,
        ),
    )

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
        doc.document_type for doc in vault._documents
    )) or ["case", "runbook", "faq"]

    search_suggestions = sorted(set(
        term for item in search_result.items
        for term in item.matched_terms
    )) if search else []

    return KnowledgeVaultResponse(
        articles=articles,
        categories=categories,
        searchSuggestions=search_suggestions,
    )


@router.get("/soc/agents", response_model=AgentGovernanceResponse)
async def get_agent_governance(
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
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
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    report_svc: ReportingService = Depends(get_reporting_service),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    lifecycle_svc: TicketLifecycleService = Depends(get_ticket_lifecycle),
):
    """Return reporting metrics and trends for SOC dashboards."""
    now = _now()
    tickets, operating_mode = await _resolve_tickets_with_mode(otrs, 25)

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

    total_points = 7
    tickets_per_point = max(1, len(tickets) // total_points) if tickets else 1
    trends: list[TrendItem] = []
    for i in range(total_points):
        day = now - timedelta(days=total_points - 1 - i)
        chunk = tickets[i * tickets_per_point:(i + 1) * tickets_per_point]
        if not chunk:
            chunk = tickets[-tickets_per_point:] if tickets else []

        day_assessments = [lifecycle_svc.assess(ticket, as_of=now) for ticket in chunk]
        breaches = sum(1 for assessment in day_assessments if assessment.risk_level.value == "critical")
        compliance = 100.0
        if day_assessments:
            compliance = max(0.0, ((len(day_assessments) - breaches) / len(day_assessments)) * 100)

        trends.append(TrendItem(
            date=day.strftime("%Y-%m-%d"),
            value=float(len(chunk)),
            metric="ticket_volume",
        ))
        trends.append(TrendItem(
            date=day.strftime("%Y-%m-%d"),
            value=round(compliance, 2),
            metric="sla_compliance",
        ))

    return ReportingResponse(
        metrics=metrics_list,
        trends=trends,
        reportTypes=["daily", "weekly", "monthly", "sla", "agent"],
        operatingMode=operating_mode,
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
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
    db: AsyncSession = Depends(get_db),
):
    """Return audit trail from agent governance events and operational records (persisted)."""
    now = _now()

    # Calculate time bounds
    try:
        time_from = datetime.fromisoformat(from_) if from_ else None
    except (ValueError, TypeError):
        time_from = None
    try:
        time_to = datetime.fromisoformat(to) if to else None
    except (ValueError, TypeError):
        time_to = None

    # Query from OperationalRecord
    records, total = await agent_svc.query_audit_events(
        db,
        actor=actor,
        action=eventType,
        from_date=time_from,
        to_date=time_to,
        limit=limit,
        offset=(page - 1) * limit,
    )

    events: list[AuditEventItem] = []
    for record in records:
        payload = record.payload or {}
        events.append(AuditEventItem(
            id=record.id,
            actor=record.actor_name or "system",
            action=record.title or "unknown",
            target=payload.get("resource_type", "unknown") + ":" + record.resource_id if record.resource_id else "unknown",
            timestamp=record.created_at.isoformat() if record.created_at else now.isoformat(),
            details=payload.get("details") or payload,
        ))

    # Build actors list from records
    actors_list = sorted(set(
        record.actor_name for record in records if record.actor_name
    ))

    return AuditResponse(
        events=events,
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
    from src.integrations.otrs_znuny import OtrsZnunySettings
    otrs_settings = OtrsZnunySettings()

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
            ConfigSetting(key="otrs_configured", value=otrs_settings.is_configured, type="boolean"),
            ConfigSetting(key="otrs_base_url", value=otrs_settings.base_url if otrs_settings.is_configured else "", type="string"),
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
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
    db: AsyncSession = Depends(get_db),
):
    """Reclassify a ticket — validate priority/queue change via QueueStrategyService."""
    ticket = await _resolve_ticket(otrs, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    previous_priority = _ticket_priority(ticket)
    previous_queue = ticket.queue.slug or "n1-triage"

    # Validate via queue strategy
    decision = queue_svc.recommend(QueueDecisionRequest(
        subject=ticket.subject,
        body_text=body.reason or ticket.subject,
        urgency=body.priority or previous_priority,
        current_tier=QueueTier.N1,
        current_locked=False,
    ))

    new_priority = _canonical_priority(body.priority or previous_priority)
    new_queue = body.queue_slug or decision.routing.queue.slug or previous_queue

    # Log the action and persist to database
    await agent_svc.persist_and_log_event(
        db,
        actor_name=current_user.username,
        action="ticket.reclassified",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "reason": body.reason,
            "new_priority": new_priority,
            "new_queue": new_queue,
            "previous_priority": previous_priority,
            "previous_queue": previous_queue,
        },
    )

    # Propagate to OTRS if available
    if otrs is not None:
        try:
            await otrs.update_ticket(
                ticket_id,
                priority=_domain_priority(new_priority),
                queue=_queue_from_slug(new_queue),
            )
        except Exception:
            pass  # Best-effort

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
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    queue_svc: QueueStrategyService = Depends(get_queue_strategy),
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
    db: AsyncSession = Depends(get_db),
):
    """Escalate a ticket — get recommendation and create approval record."""
    ticket = await _resolve_ticket(otrs, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # CE-03: hierarchy-aware N-level escalation over the persisted topology.
    # Current tier comes from the ticket's real queue; honor an explicit target.
    plan = EscalationService(queue_svc).escalate(EscalationRequest(
        current_queue_slug=ticket.queue.slug,
        target_tier=QueueTier(body.target_tier) if body.target_tier else None,
        reason=body.reason,
    ))

    escalation_level = plan.level
    target_queue = plan.to_queue.slug or "n2-resolucion"

    # Create an approval record via AgentGovernanceService
    rec_response = agent_svc.recommend(AgentRecommendationRequest(
        subject=ticket.subject,
        body_text=body.reason,
        customer=ticket.customer_email,
        current_tier=plan.to_tier,
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

    # Log the action and persist to database
    await agent_svc.persist_and_log_event(
        db,
        actor_name=current_user.username,
        action="ticket.escalated",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "reason": body.reason,
            "target_tier": body.target_tier or plan.to_tier.value,
            "escalation_level": escalation_level,
            "target_queue": target_queue,
        },
    )

    # Propagate to OTRS if available
    if otrs is not None:
        try:
            await otrs.update_ticket(
                ticket_id,
                state=_domain_state("in_progress"),
                priority=_domain_priority("critical"),
                queue=_queue_from_slug(target_queue),
            )
        except Exception:
            pass  # Best-effort

    # CE-04: record the escalation in the history (best-effort)
    try:
        await EscalationRecordService(db).record(
            ticket_id=ticket_id,
            actor_name=current_user.username,
            plan=plan,
            reason=body.reason,
        )
    except Exception:
        pass  # Best-effort: recording must never break the escalate flow

    return EscalateResponse(
        ticket_id=ticket_id,
        escalation_level=escalation_level,
        target_queue=target_queue,
    )


@router.get("/soc/tickets/{ticket_id}/escalations", response_model=EscalationHistoryResponse)
async def get_ticket_escalations(
    ticket_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the escalation history for a ticket (CE-04)."""
    records = await EscalationRecordService(db).list_for_ticket(ticket_id, limit=limit)
    items = [EscalationRecordService.to_item(r) for r in records]
    return EscalationHistoryResponse(
        ticket_id=ticket_id,
        total=len(items),
        items=items,
    )


@router.post("/soc/tickets/{ticket_id}/notes", response_model=AddNoteResponse)
async def post_add_note(
    ticket_id: str,
    body: AddNoteRequest,
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(RateLimiter(30)),
    otrs: OtrsZnunyClient | None = Depends(get_otrs_client),
    agent_svc: AgentGovernanceService = Depends(_get_agent_governance_service),
    db: AsyncSession = Depends(get_db),
):
    """Add an internal note to a ticket and record the audit event."""
    ticket = await _resolve_ticket(otrs, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    note_id = str(uuid4())

    # Create audit event via AgentGovernanceService and persist to database
    await agent_svc.persist_and_log_event(
        db,
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

    # Propagate to OTRS if available — create the article for real
    if otrs is not None:
        try:
            article_draft = ArticleDraft(
                author_kind=ActorKind.HUMAN,
                author_name=current_user.username,
                body_text=body.content,
                subject=f"Note ({body.visibility})",
            )
            article = await otrs.add_article(ticket_id, article_draft)
            note_id = article.id  # Use the real article ID from OTRS
        except Exception:
            pass  # Keep the generated note_id

    return AddNoteResponse(
        ticket_id=ticket_id,
        note_id=note_id,
    )