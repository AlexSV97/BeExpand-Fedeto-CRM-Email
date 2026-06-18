# Design: CE-03 — Escalado N-niveles

## Technical Approach

`EscalationService` wraps a `QueueStrategyService` and computes an
`EscalationPlan` over the topology tier chain. The chain is the topology roots
sorted by tier rank (n1<n2<n3); the current tier is resolved from a queue slug
or passed explicitly; the target is an explicit tier (if higher) or the next
level up. The plan includes a `steps` path enumerating every tier traversed. The
service is pure logic (no I/O). It is exposed via `POST /queues/escalate` and the
SOC escalate endpoint is rewired to use it.

## Architecture Decisions

### Decision: Chain by tier rank vs parent_id traversal

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Order roots by tier rank (n1<n2<n3) | Matches CE-01 seed (N-tiers are roots) and existing `_tier_rank` logic | **Chosen** |
| Follow `parent_id` links | CE-01 seed parents only specials → tiers, so no N-chain exists | Rejected for this change |

### Decision: New service vs extend QueueStrategyService

| Option | Tradeoff | Decision |
|--------|----------|----------|
| New `EscalationService(strategy)` | Keeps routing vs escalation concerns separate; small surface | **Chosen** |
| Add methods to `QueueStrategyService` | Grows an already large class | Rejected |

### Decision: No-op semantics

Target ≤ current, or already at top tier → `should_escalate=False`, `to_tier =
from_tier`, empty `steps`. The caller decides whether to act. This keeps
`escalate()` total (never raises).

## Data Flow

```
POST /queues/escalate  /  SOC escalate
        │
        ▼
QueueStrategyService.topology() ──► tier chain [n1,n2,n3] (+specials)
        │
        ▼
EscalationService.escalate(req)
   resolve current tier (slug → tier | current_tier | N1)
   target = target_tier (if rank↑) | next level | none
   build steps current+1 .. target
        │
        ▼
   EscalationPlan(should_escalate, from/to tier+queue, level, steps, reason)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/escalation.py` | Create | Models + `EscalationService` |
| `src/api/routers/queues.py` | Modify | `POST /queues/escalate` |
| `src/api/routers/soc.py` | Modify | escalate endpoint uses `EscalationService` |
| `tests/test_escalation.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
class EscalationRequest(BaseModel):
    current_tier: QueueTier = QueueTier.N1
    current_queue_slug: str | None = None
    target_tier: QueueTier | None = None
    reason: str | None = None

class EscalationStep(BaseModel):
    tier: QueueTier
    queue: Queue
    level: int

class EscalationPlan(BaseModel):
    should_escalate: bool
    from_tier: QueueTier
    to_tier: QueueTier
    from_queue: Queue | None
    to_queue: Queue
    level: int                 # rank of to_tier
    steps: list[EscalationStep]
    reason: str

class EscalationService:
    def __init__(self, strategy: QueueStrategyService)
    def escalate(self, request: EscalationRequest) -> EscalationPlan
```

Tier rank: `n1=1, n2=2, n3=3, special=4`. `to_queue` for a tier is the topology
node with that tier (the single root for n1/n2/n3; the first special for special).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | auto next-level (Scenario 1) | N1 no target → N2, level 2 |
| Unit | explicit target + path (Scenario 2) | N1→N3 → steps [N2,N3] |
| Unit | no-op on lower target (Scenario 3) | N2 target n1 → should_escalate False |
| Unit | top tier no-op (Scenario 4) | N3 no target → should_escalate False |
| Unit | resolve from slug (Scenario 5) | slug n2-resolucion → from N2, to N3 |
| Integration | `/queues/escalate` (Scenario 6) | client + auth → 200 + shape |
| Regression | SOC escalate (Scenario 7) | existing TestPostEscalateTicket passes |

## Migration / Rollout

Additive, no schema change. Rollback = revert SOC endpoint + remove route +
delete service.

## Open Questions

- [ ] ¿Escalar una cola *special* tiene siguiente nivel? (Hipótesis: las
  especiales son terminales; `should_escalate=False` salvo `target_tier` explícito
  de mayor rango — fuera del chain N1/N2/N3 no hay auto-siguiente.)
