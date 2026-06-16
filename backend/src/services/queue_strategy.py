from __future__ import annotations

import unicodedata
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import Queue


class QueueTier(str, Enum):
    N1 = "n1"
    N2 = "n2"
    N3 = "n3"
    SPECIAL = "special"


class QueueTopologyNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    tier: QueueTier
    queue: Queue
    owner: str
    children: list["QueueTopologyNode"] = Field(default_factory=list)


class QueueTopology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: list[QueueTopologyNode] = Field(default_factory=list)
    special_queues: list[QueueTopologyNode] = Field(default_factory=list)


class QueueDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body_text: str
    urgency: str = "media"
    category: str | None = None
    current_tier: QueueTier = QueueTier.N1
    current_owner: str | None = None
    current_locked: bool = False


class QueueRoutingRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: QueueTier
    queue: Queue
    owner: str
    lock: bool
    reason: str
    motivation: str
    confidence: float


class EscalationRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_escalate: bool
    from_tier: QueueTier
    to_tier: QueueTier
    queue: Queue
    owner: str
    lock: bool
    reason: str
    motivation: str
    confidence: float


class QueueDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topology: QueueTopology
    routing: QueueRoutingRecommendation
    escalation: EscalationRecommendation


def _fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


class QueueStrategyService:
    def __init__(self) -> None:
        self._topology = QueueTopology(
            roots=[
                QueueTopologyNode(
                    name="N1 - Triage",
                    tier=QueueTier.N1,
                    queue=Queue(name="N1 - Triage", slug="n1-triage", metadata={"tier": "n1"}),
                    owner="N1 Triage",
                ),
                QueueTopologyNode(
                    name="N2 - Resolución",
                    tier=QueueTier.N2,
                    queue=Queue(name="N2 - Resolución", slug="n2-resolucion", metadata={"tier": "n2"}),
                    owner="N2 Resolver",
                ),
                QueueTopologyNode(
                    name="N3 - Ingeniería",
                    tier=QueueTier.N3,
                    queue=Queue(name="N3 - Ingeniería", slug="n3-ingenieria", metadata={"tier": "n3"}),
                    owner="N3 Engineering",
                ),
            ],
            special_queues=[
                QueueTopologyNode(
                    name="Special - Fabricante",
                    tier=QueueTier.SPECIAL,
                    queue=Queue(
                        name="Special - Fabricante",
                        slug="special-fabricante",
                        metadata={"tier": "special", "kind": "fabricante"},
                    ),
                    owner="Vendor Coordinator",
                ),
                QueueTopologyNode(
                    name="Special - External ITSM",
                    tier=QueueTier.SPECIAL,
                    queue=Queue(
                        name="Special - External ITSM",
                        slug="special-external-itsm",
                        metadata={"tier": "special", "kind": "external_itsm"},
                    ),
                    owner="ITSM Integrations",
                ),
                QueueTopologyNode(
                    name="Special - Seguridad",
                    tier=QueueTier.SPECIAL,
                    queue=Queue(
                        name="Special - Seguridad",
                        slug="special-seguridad",
                        metadata={"tier": "special", "kind": "security"},
                    ),
                    owner="Security Desk",
                ),
            ],
        )

    def topology(self) -> QueueTopology:
        return self._topology

    def recommend(self, request: QueueDecisionRequest) -> QueueDecision:
        routing = self._route(request)
        escalation = self._recommend_escalation(request, routing)
        return QueueDecision(topology=self._topology, routing=routing, escalation=escalation)

    def _route(self, request: QueueDecisionRequest) -> QueueRoutingRecommendation:
        text = _fold(f"{request.subject} {request.body_text}")

        special_match = self._match_special_queue(text)
        if special_match is not None:
            queue_name, owner, reason, motivation = special_match
            return QueueRoutingRecommendation(
                tier=QueueTier.SPECIAL,
                queue=self._queue_for_special(queue_name),
                owner=owner,
                lock=True,
                reason=reason,
                motivation=motivation,
                confidence=0.94,
            )

        if self._has_any(text, ("root cause", "code level", "hotfix", "patch", "engineering", "source code", "regression")):
            return QueueRoutingRecommendation(
                tier=QueueTier.N3,
                queue=self._queue_for_tier(QueueTier.N3),
                owner="N3 Engineering",
                lock=True,
                reason="Matched N3 keywords: root cause / hotfix / engineering work needed.",
                motivation="Escalar a ingeniería para resolver la causa raíz y reducir riesgo operativo.",
                confidence=0.9,
            )

        if self._has_any(text, ("error", "timeout", "incident", "bug", "failure", "blocked", "issue", "troubleshoot")):
            return QueueRoutingRecommendation(
                tier=QueueTier.N2,
                queue=self._queue_for_tier(QueueTier.N2),
                owner="N2 Resolver",
                lock=True,
                reason="Matched N2 keywords: incident / error / timeout / bug.",
                motivation="Escalar a resolución especializada antes de que el incidente escale en SLA.",
                confidence=0.82,
            )

        return QueueRoutingRecommendation(
            tier=QueueTier.N1,
            queue=self._queue_for_tier(QueueTier.N1),
            owner="N1 Triage",
            lock=False,
            reason="No escalation keywords matched; keep the case in triage.",
            motivation="Mantener el ticket en N1 evita handoffs innecesarios y acelera el primer toque.",
            confidence=0.66,
        )

    def _recommend_escalation(
        self,
        request: QueueDecisionRequest,
        routing: QueueRoutingRecommendation,
    ) -> EscalationRecommendation:
        current_rank = self._tier_rank(request.current_tier)
        routing_rank = self._tier_rank(routing.tier)
        should_escalate = routing_rank > current_rank

        if should_escalate:
            return EscalationRecommendation(
                should_escalate=True,
                from_tier=request.current_tier,
                to_tier=routing.tier,
                queue=routing.queue,
                owner=routing.owner,
                lock=True,
                reason=routing.reason,
                motivation=routing.motivation,
                confidence=routing.confidence,
            )

        current_owner = request.current_owner or self._owner_for_tier(request.current_tier)
        return EscalationRecommendation(
            should_escalate=False,
            from_tier=request.current_tier,
            to_tier=request.current_tier,
            queue=self._queue_for_tier(request.current_tier),
            owner=current_owner,
            lock=request.current_locked,
            reason="No escalation needed; the current queue is sufficient.",
            motivation="Keep ownership stable and avoid unnecessary queue movement.",
            confidence=max(routing.confidence - 0.15, 0.5),
        )

    def _queue_for_tier(self, tier: QueueTier) -> Queue:
        for node in self._topology.roots:
            if node.tier == tier:
                return node.queue
        raise ValueError(f"Unknown queue tier: {tier}")

    def _queue_for_special(self, name: str) -> Queue:
        for node in self._topology.special_queues:
            if node.name == name:
                return node.queue
        raise ValueError(f"Unknown special queue: {name}")

    @staticmethod
    def _tier_rank(tier: QueueTier) -> int:
        ranks = {
            QueueTier.N1: 1,
            QueueTier.N2: 2,
            QueueTier.N3: 3,
            QueueTier.SPECIAL: 4,
        }
        return ranks[tier]

    @staticmethod
    def _owner_for_tier(tier: QueueTier) -> str:
        return {
            QueueTier.N1: "N1 Triage",
            QueueTier.N2: "N2 Resolver",
            QueueTier.N3: "N3 Engineering",
            QueueTier.SPECIAL: "Vendor Coordinator",
        }[tier]

    def _match_special_queue(self, text: str) -> tuple[str, str, str, str] | None:
        vendor_terms = ("fabricante", "vendor", "manufacturer", "oem", "firmware")
        itsm_terms = ("external itsm", "itsm", "servicenow", "zendesk", "remedy")
        security_terms = ("phishing", "malware", "security", "breach", "ioc")

        if self._has_any(text, vendor_terms):
            return (
                "Special - Fabricante",
                "Vendor Coordinator",
                "Matched special queue keywords: manufacturer / vendor / firmware.",
                "Escalar al fabricante preservando contexto y ownership hasta que haya respuesta.",
            )
        if self._has_any(text, itsm_terms):
            return (
                "Special - External ITSM",
                "ITSM Integrations",
                "Matched special queue keywords: external ITSM / service desk handoff.",
                "Enviar el caso al sistema externo correcto con tracking y auditoría.",
            )
        if self._has_any(text, security_terms):
            return (
                "Special - Seguridad",
                "Security Desk",
                "Matched special queue keywords: security / phishing / malware.",
                "Bloquear y escalar al equipo de seguridad para contención inmediata.",
            )
        return None

    @staticmethod
    def _has_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)


async def get_queue_strategy_service() -> QueueStrategyService:
    yield QueueStrategyService()
