"""EscalationService — CE-03.

Escalado N-niveles sobre la topología de colas persistida (CE-01). Calcula un
``EscalationPlan`` recorriendo la cadena de tiers (N1→N2→N3) de la topología,
hacia un tier objetivo explícito o, por defecto, al siguiente nivel. Lógica pura
(sin I/O): la topología la aporta el ``QueueStrategyService`` inyectado.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import Queue
from src.services.queue_strategy import (
    QueueStrategyService,
    QueueTier,
    QueueTopologyNode,
)


_TIER_RANK: dict[QueueTier, int] = {
    QueueTier.N1: 1,
    QueueTier.N2: 2,
    QueueTier.N3: 3,
    QueueTier.SPECIAL: 4,
}


class EscalationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_tier: QueueTier = QueueTier.N1
    current_queue_slug: str | None = None
    target_tier: QueueTier | None = None
    reason: str | None = None


class EscalationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: QueueTier
    queue: Queue
    level: int


class EscalationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_escalate: bool
    from_tier: QueueTier
    to_tier: QueueTier
    from_queue: Queue | None
    to_queue: Queue
    level: int
    steps: list[EscalationStep] = Field(default_factory=list)
    reason: str


class EscalationService:
    def __init__(self, strategy: QueueStrategyService) -> None:
        self._strategy = strategy

    # ── Topología ────────────────────────────────────────────────────────
    def _nodes(self) -> list[QueueTopologyNode]:
        topology = self._strategy.topology()
        return [*topology.roots, *topology.special_queues]

    def _chain(self) -> list[QueueTopologyNode]:
        """Cadena de escalado: tiers N (no especiales) ordenados por rango."""
        chain = [n for n in self._nodes() if n.tier != QueueTier.SPECIAL]
        chain.sort(key=lambda n: _TIER_RANK[n.tier])
        return chain

    def _node_for_tier(self, tier: QueueTier) -> QueueTopologyNode | None:
        return next((n for n in self._nodes() if n.tier == tier), None)

    def _tier_for_slug(self, slug: str) -> QueueTier | None:
        node = next((n for n in self._nodes() if n.queue.slug == slug), None)
        return node.tier if node else None

    # ── Escalado ─────────────────────────────────────────────────────────
    def escalate(self, request: EscalationRequest) -> EscalationPlan:
        """Calcula el plan de escalado. Nunca lanza (REQ-1)."""
        # REQ-3: tier actual desde slug, o explícito, o N1 por defecto.
        from_tier = request.current_tier
        if request.current_queue_slug:
            resolved = self._tier_for_slug(request.current_queue_slug)
            from_tier = resolved if resolved is not None else QueueTier.N1

        from_node = self._node_for_tier(from_tier)
        from_queue = from_node.queue if from_node else None

        chain = self._chain()
        max_rank = max((_TIER_RANK[n.tier] for n in chain), default=_TIER_RANK[from_tier])
        from_rank = _TIER_RANK[from_tier]

        # Determinar tier objetivo.
        if request.target_tier is not None:
            target_rank = _TIER_RANK[request.target_tier]
            if target_rank <= from_rank:  # REQ-5: objetivo no superior → no-op
                return self._noop(from_tier, from_queue, "El tier objetivo no es superior al actual.")
            to_tier = request.target_tier
        else:
            # REQ-4: siguiente nivel; si ya está en el tope, no-op.
            if from_rank >= max_rank:
                return self._noop(from_tier, from_queue, "El ticket ya está en el tier más alto de la cadena.")
            target_rank = from_rank + 1
            to_node = next((n for n in chain if _TIER_RANK[n.tier] == target_rank), None)
            if to_node is None:
                return self._noop(from_tier, from_queue, "No hay un tier superior disponible en la topología.")
            to_tier = to_node.tier

        to_node = self._node_for_tier(to_tier)
        if to_node is None:
            return self._noop(from_tier, from_queue, "El tier objetivo no existe en la topología.")

        # REQ-6: construir el camino de niveles intermedios (current+1 .. target).
        steps = self._build_steps(from_rank, _TIER_RANK[to_tier], chain, to_node)

        return EscalationPlan(
            should_escalate=True,
            from_tier=from_tier,
            to_tier=to_tier,
            from_queue=from_queue,
            to_queue=to_node.queue,
            level=_TIER_RANK[to_tier],
            steps=steps,
            reason=request.reason or f"Escalado de {from_tier.value} a {to_tier.value}.",
        )

    def _build_steps(
        self,
        from_rank: int,
        to_rank: int,
        chain: list[QueueTopologyNode],
        to_node: QueueTopologyNode,
    ) -> list[EscalationStep]:
        steps: list[EscalationStep] = []
        for rank in range(from_rank + 1, to_rank + 1):
            node = next((n for n in chain if _TIER_RANK[n.tier] == rank), None)
            if node is None and rank == to_rank:
                node = to_node  # objetivo fuera de la cadena (p.ej. special)
            if node is not None:
                steps.append(EscalationStep(tier=node.tier, queue=node.queue, level=rank))
        return steps

    @staticmethod
    def _noop(from_tier: QueueTier, from_queue: Queue | None, reason: str) -> EscalationPlan:
        # to_queue no puede ser None; si no hay cola actual, sintetiza una mínima.
        queue = from_queue or Queue(name=from_tier.value, slug=from_tier.value)
        return EscalationPlan(
            should_escalate=False,
            from_tier=from_tier,
            to_tier=from_tier,
            from_queue=from_queue,
            to_queue=queue,
            level=_TIER_RANK[from_tier],
            steps=[],
            reason=reason,
        )
