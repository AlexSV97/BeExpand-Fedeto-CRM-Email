# Design: CE-06 — Escalado a fabricante / ITSM externo

## Technical Approach

`ExternalEscalationService` maps a destination to a CE-01 special queue, validates
it against the live topology, mints an `ExternalRef` tracking reference, and
persists the handoff as an `OperationalRecord` (`record_kind="external_escalation"`).
The SOC endpoint records the handoff and best-effort moves the OTRS ticket to the
special queue. Mirrors CE-04/CE-05 recording patterns; no new table. Real outbound
delivery to a vendor/ITSM API is left as a future integration — the tracking ref is
the durable, queryable artifact.

## Architecture Decisions

### Decision: Record the tracking ref vs call an external API now

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Persist `ExternalRef` + handoff record | Traceable now; vendor-agnostic; no external creds needed | **Chosen** |
| Integrate a concrete vendor/ITSM API | Real delivery, but needs creds/contracts per tenant | Deferred (out of scope) |

### Decision: Reuse special queues from CE-01

The special queues (`special-fabricante`, `special-external-itsm`) already model
external destinations. CE-06 routes to them rather than inventing new targets.

## Data Flow

```
POST /soc/tickets/{id}/escalate-external {destination, reason?, external_id?}
        │
        ▼
ExternalEscalationService(db, strategy)
   destination → special slug ; validate ∈ topology.special_queues
   tracking = ExternalRef(system=destination, entity_type="external_case",
                          external_id=provided|generated)
        ▼
OperationalRecord(record_kind="external_escalation", resource_id=id,
                  status="sent", payload={destination, queue_slug, tracking_ref, reason})
        │ best-effort otrs.update_ticket(queue=special)
        ▲
GET /soc/tickets/{id}/external-escalations → list_for_ticket(id)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/external_escalation.py` | Create | Service + models |
| `src/api/routers/soc.py` | Modify | escalate-external + history endpoints |
| `tests/test_external_escalation.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
EXTERNAL_ESCALATION_RECORD_KIND = "external_escalation"

DESTINATION_QUEUE = {"fabricante": "special-fabricante",
                     "external_itsm": "special-external-itsm"}
DESTINATION_PREFIX = {"fabricante": "FAB", "external_itsm": "ITSM"}

class ExternalEscalationResult(BaseModel):
    ticket_id: str
    destination: str
    queue_slug: str
    tracking_ref: ExternalRef     # domain model reused
    status: str = "sent"
    created_at: str

class ExternalEscalationHistoryResponse(BaseModel):
    ticket_id: str
    total: int
    items: list[ExternalEscalationResult]

class ExternalEscalationService:
    def __init__(self, db: AsyncSession, strategy: QueueStrategyService)
    async def escalate(self, *, ticket_id, destination, actor_name,
                       reason=None, external_id=None) -> ExternalEscalationResult
    async def list_for_ticket(self, ticket_id, limit=50) -> list[OperationalRecord]
    @staticmethod
    def to_item(record) -> ExternalEscalationResult
    # raises ValueError on unknown destination / missing queue
```

Endpoint request validates `destination ∈ DESTINATION_QUEUE` (→ 422 otherwise).
Generated external id: `f"{PREFIX}-{uuid4().hex[:8].upper()}"`. Records use an
explicit microsecond `created_at` (deterministic ordering, as in CE-05).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | manufacturer → special queue (Sc.1) | in-memory DB + hardcoded topology |
| Unit | provided external id (Sc.2) | external_id passthrough |
| Unit | generated external id (Sc.3) | non-empty when omitted |
| Unit | persisted + listable (Sc.4) | list_for_ticket |
| Integration | unknown destination → 422 (Sc.5) | endpoint |
| Integration | round-trip (Sc.6) | escalate-external → GET history |
| Integration | auth (Sc.7) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoints + service.

## Open Questions

- [ ] ¿Añadir destino `seguridad` (`special-seguridad`)? Se deja fuera: el backlog
  CE-06 cita fabricante / ITSM externo; ampliar el mapa es trivial si se requiere.
