# Design: CE-05 — Gestión de owner/lock por ticket

## Technical Approach

Track ownership and lock as a sequence of `OperationalRecord` rows
(`record_kind="ownership"`), each storing the full resulting state snapshot
(`owner`, `locked`, `locked_by`) plus the action and actor. `current_state()` is
the latest snapshot, so reads are a single ordered query. `TicketOwnershipService`
computes new state from previous + action. SOC endpoints persist changes and, on
assign, propagate the owner to OTRS best-effort. Mirrors CE-04's recording pattern;
no new table.

## Architecture Decisions

### Decision: Snapshot-per-record vs event-replay

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Store full state snapshot each change | `current_state` = latest row; trivial reads | **Chosen** |
| Store deltas and replay | Smaller rows, but reconstruct on every read | Rejected (needless complexity) |

### Decision: Reuse OperationalRecord vs new table

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `OperationalRecord` + `record_kind="ownership"` | No migration; consistent with escalation/audit | **Chosen** |
| Dedicated `ticket_ownership` table | Stronger schema for homogeneous JSON | Rejected for this change |

### Decision: Advisory lock vs enforced lock

Lock state is **advisory** (recorded, queryable) — enforcement across concurrent
writers is out of scope. Documented in the spec.

## Data Flow

```
POST /soc/tickets/{id}/assign|lock|unlock
        │
        ▼
TicketOwnershipService(db): prev = current_state(); new = apply(action, prev)
        ▼
OperationalRecord(record_kind="ownership", resource_id=id,
                  status=action, payload={action,actor,reason,state:new})
        │ (assign) best-effort otrs.update_ticket(owner=new.owner)
        ▲
GET /soc/tickets/{id}/ownership → current_state() + list_history()
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/ticket_ownership.py` | Create | Service + models |
| `src/api/routers/soc.py` | Modify | assign/lock/unlock + ownership endpoints |
| `tests/test_ticket_ownership.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
OWNERSHIP_RECORD_KIND = "ownership"

class OwnershipState(BaseModel):
    owner: str | None = None
    locked: bool = False
    locked_by: str | None = None

class OwnershipResponse(BaseModel):
    ticket_id: str
    state: OwnershipState
    history: list[OwnershipHistoryItem]

class OwnershipHistoryItem(BaseModel):
    id: str
    ticket_id: str
    action: str
    actor: str | None
    owner: str | None
    locked: bool
    locked_by: str | None
    reason: str | None
    created_at: str

class AssignRequest(BaseModel):
    owner: str           # validated non-empty
    reason: str = ""     # max 500

class TicketOwnershipService:
    def __init__(self, db: AsyncSession)
    async def assign(self, ticket_id, owner, actor_name, reason=None) -> OperationalRecord
    async def lock(self, ticket_id, actor_name, reason=None) -> OperationalRecord
    async def unlock(self, ticket_id, actor_name, reason=None) -> OperationalRecord
    async def current_state(self, ticket_id) -> OwnershipState
    async def list_history(self, ticket_id, limit=50) -> list[OperationalRecord]
    @staticmethod
    def to_item(record) -> OwnershipHistoryItem
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | assign sets owner (Sc.1) | in-memory DB |
| Unit | lock sets locked+locked_by (Sc.2) | preserve owner |
| Unit | unlock clears lock keeps owner (Sc.3) | |
| Unit | latest-wins current_state (Sc.4) | assign→lock→unlock |
| Unit | empty default (Sc.5) | unknown ticket |
| Integration | assign endpoint round-trip (Sc.6) | client assign → GET ownership |
| Integration | auth (Sc.7) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoints + service.

## Open Questions

- [ ] ¿Owner debe mapear a `Ticket.owner` o `Ticket.assigned_to` en OTRS?
  (Hipótesis: `owner`; `update_ticket` acepta ambos, se propaga `owner`.)
