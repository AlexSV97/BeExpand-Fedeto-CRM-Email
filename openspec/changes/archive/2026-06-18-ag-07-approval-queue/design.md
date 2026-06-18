# Design: AG-07 — Cola de aprobaciones pendientes

## Technical Approach

Add `list_pending_approvals` to `AgentGovernanceService`, querying the
`OperationalRecord` rows it already writes (`record_kind="agent_recommendation"`,
`status="pending"`), and expose it via `GET /agents/approvals/pending` reusing the
existing serialization (`OperationalHistoryResponse`). No new table; closes the
human-in-the-loop loop already half-built (recommend → [pending] → approve/reject).

## Architecture Decisions

### Decision: Query status="pending" vs a separate queue table

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Filter existing `agent_recommendation` rows by `status="pending"` | No new storage; `persist_approval` already flips the status | **Chosen** |
| Dedicated approval-queue table | Redundant with the records already written | Rejected |

## Data Flow

```
POST /agents/recommendation → OperationalRecord(kind=agent_recommendation,
                                status = "pending" if requires_approval else "auto_approved")
GET  /agents/approvals/pending → list_pending_approvals() → rows with status="pending"
POST /agents/approvals → persist_approval() sets status=approved|rejected → leaves the queue
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/agent_governance.py` | Modify | `list_pending_approvals(db, limit)` |
| `src/api/routers/agents.py` | Modify | `GET /agents/approvals/pending` |
| `tests/test_agent_approval_queue.py` | Create | Unit + endpoint |

## Interfaces / Contracts

```python
class AgentGovernanceService:
    async def list_pending_approvals(self, db: AsyncSession, limit: int = 50) -> list[OperationalRecord]
```

Endpoint returns the existing `OperationalHistoryResponse` (`items`, `total`) via
`_serialize_record`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | pending listed (Sc.1) | persist a requires_approval recommendation → appears |
| Unit | auto-approved not listed (Sc.2) | non-critical recommendation → absent |
| Unit | approve removes (Sc.3) | persist_approval → no longer pending |
| Integration | endpoint (Sc.4) | client → 200 + items/total |
| Integration | auth (Sc.5) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoint + method.

## Open Questions

- [ ] ¿Paginación/orden configurable? `limit` cubre el MVP.
