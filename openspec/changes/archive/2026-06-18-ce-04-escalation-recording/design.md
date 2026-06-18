# Design: CE-04 — Registro de escalados

## Technical Approach

Persist escalations as `OperationalRecord` rows with `record_kind="escalation"`,
mirroring how `agent_recommendation`, `agent_approval` and `audit_event` are
stored — no new table. `EscalationRecordService` wraps an `AsyncSession` and
offers record/query methods. The SOC escalate endpoint records the computed
`EscalationPlan` as a best-effort side-effect and a new history endpoint reads it
back, serialized into a small API model.

## Architecture Decisions

### Decision: Reuse OperationalRecord vs new escalations table

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `OperationalRecord` + `record_kind="escalation"` | No migration; consistent with existing records; queryable by kind/resource | **Chosen** |
| Dedicated `escalations` table | Stronger schema, but a migration + model for a homogeneous JSON payload | Rejected for this change |

### Decision: Best-effort recording

The recording call in the escalate endpoint is wrapped so a failure never alters
the response (NFR-2), matching the existing best-effort OTRS propagation there.

## Data Flow

```
POST /soc/tickets/{id}/escalate
        │  (CE-03) EscalationService.escalate() → plan
        ▼
EscalationRecordService(db).record(ticket_id, actor, plan)
        ▼
OperationalRecord(record_kind="escalation", resource_id=ticket_id,
                  status="escalated"|"noop", payload=plan.json)
        ▲
GET /soc/tickets/{id}/escalations → list_for_ticket(id) → [EscalationHistoryItem]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/escalation_recording.py` | Create | `EscalationRecordService` + `EscalationHistoryItem` + `EscalationHistoryResponse` |
| `src/api/routers/soc.py` | Modify | record on escalate (best-effort) + `GET .../escalations` |
| `tests/test_escalation_recording.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
ESCALATION_RECORD_KIND = "escalation"

class EscalationHistoryItem(BaseModel):
    id: str
    ticket_id: str
    actor_name: str | None
    from_tier: str | None
    to_tier: str | None
    to_queue: str | None
    level: int | None
    should_escalate: bool
    reason: str | None
    created_at: str

class EscalationHistoryResponse(BaseModel):
    ticket_id: str
    total: int
    items: list[EscalationHistoryItem]

class EscalationRecordService:
    def __init__(self, db: AsyncSession)
    async def record(self, *, ticket_id: str, actor_name: str,
                     plan: EscalationPlan, reason: str | None = None) -> OperationalRecord
    async def list_for_ticket(self, ticket_id: str, limit: int = 50) -> list[OperationalRecord]
    async def list_all(self, limit: int = 50) -> list[OperationalRecord]
    @staticmethod
    def to_item(record: OperationalRecord) -> EscalationHistoryItem
```

`payload` stores `{"plan": plan.model_dump(mode="json"), "reason": reason}`.
`to_item` reads tier/queue/level from `payload["plan"]`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | record persists row (Scenario 1) | in-memory DB → assert kind/resource/status |
| Unit | no-op status (Scenario 2) | plan should_escalate False → status "noop" |
| Unit | newest-first (Scenario 3) | two records → order |
| Unit | ticket-scoped (Scenario 4) | two tickets → filter |
| Integration | escalate creates record (Scenario 5) | client escalate → GET escalations ≥1 |
| Integration | auth (Scenario 6) | no header → 401 |
| Integration | best-effort (Scenario 7) | monkeypatch record to raise → escalate still 200 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoint + recording call + service;
existing rows stay inert.

## Open Questions

- [ ] ¿Exponer también un histórico global `GET /soc/escalations`? (Se incluye
  `list_all()` en el servicio por si se necesita; el endpoint inicial es
  per-ticket.)
