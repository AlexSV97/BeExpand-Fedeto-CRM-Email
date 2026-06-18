# Design: CP-01 — Bandeja inteligente

## Technical Approach

Extend `TicketItem` with operational context and compute it per row in
`GET /soc/tickets` through a small resilient helper, reusing services already
injected into the endpoint: `TicketLifecycleService` (SLA risk, SLA-04) and
`QueueStrategyService.recommend` (rule-based suggested queue, CE-02 fast path).
No new endpoint, no schema change.

## Architecture Decisions

### Decision: Rule-based suggestion per row vs LLM

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `QueueStrategyService.recommend` (rules) | Deterministic, microseconds, no I/O | **Chosen** |
| LLM suggestion (CE-02) per row | High latency × N rows; nondeterministic | Rejected for the list (kept on its endpoint) |

### Decision: Resilient per-row enrichment

Each row's enrichment is wrapped so a single bad ticket leaves its enriched fields
null instead of failing the whole list (NFR/REQ-5).

## Data Flow

```
GET /soc/tickets
   tickets = _resolve_tickets_with_mode(otrs)
   for t in page:
       _enrich_ticket_item(t, queue_svc, lifecycle_svc)
         slaRisk/remaining ← lifecycle.assess(t)        (if t.sla)
         suggestedQueue   ← queue_svc.recommend(t).routing.queue.slug
         owner/queue      ← t.owner / t.queue.slug
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/api/routers/soc.py` | Modify | `TicketItem` fields + `_enrich_ticket_item`; queue endpoint uses it |
| `tests/test_smart_inbox.py` | Create | Enrichment + endpoint tests |

## Interfaces / Contracts

```python
class TicketItem(BaseModel):
    id: str; subject: str; status: str; priority: str
    assignee: str | None = None
    createdAt: str; updatedAt: str
    owner: str | None = None
    queue: str | None = None
    slaRisk: str | None = None
    slaRemainingMinutes: float | None = None
    suggestedQueue: str | None = None

def _enrich_ticket_item(t, queue_svc, lifecycle_svc) -> TicketItem
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | enrich computes risk + suggested queue | craft ticket → assert fields |
| Unit | no-SLA ticket → null risk | sla=None |
| Unit | resilient to assess failure | monkeypatch assess to raise → row still built |
| Integration | endpoint rows enriched (Sc.1-3) | client GET → assert fields present/valid |
| Regression | filtering preserved (Sc.4) | existing TestGetTicketQueue passes |

## Migration / Rollout

Additive, no schema change. Rollback = revert fields + helper.

## Open Questions

- [ ] ¿Permitir ordenar/filtrar por `slaRisk`/`suggestedQueue`? Fuera de alcance;
  el front puede ordenar client-side de momento.
