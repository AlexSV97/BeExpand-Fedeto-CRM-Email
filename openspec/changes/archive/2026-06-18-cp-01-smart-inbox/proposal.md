# Proposal: CP-01 — Bandeja inteligente

## Intent

Backlog story CP-01 (Épica 4): "La lista muestra prioridad, riesgo SLA, cola
sugerida y owner". The ticket queue (`GET /soc/tickets`) today returns only
id/subject/status/priority/assignee/timestamps. This enriches each row with the
operational context an analyst needs to triage at a glance — SLA risk (SLA-04),
suggested queue (CE-02 rule path), owner and current queue — turning the list
into a smart inbox.

## Scope

### In Scope
- Extend `TicketItem` with `owner`, `queue`, `slaRisk`, `slaRemainingMinutes`,
  `suggestedQueue`
- Enrich each row in `GET /soc/tickets` via `TicketLifecycleService` (risk) and
  `QueueStrategyService.recommend` (suggested queue, rule-based)
- Resilient enrichment (a per-ticket failure never breaks the list)
- Tests

### Out of Scope
- LLM-based queue suggestion per row (uses the fast rule path to avoid latency;
  the AI suggestion stays on its own endpoint, CE-02)
- Frontend rendering
- New filters/sorting by the new fields

## Capabilities

### New Capabilities
- none (extends the existing `ticket-queue` surface)

### Modified Capabilities
- `ticket-queue`: rows carry SLA risk + suggested queue + owner

## Approach
1. Add fields to `TicketItem`.
2. `_enrich_ticket_item(ticket, queue_svc, lifecycle_svc)` computes SLA risk +
   remaining (if the ticket has an SLA) and a rule-based suggested queue.
3. `GET /soc/tickets` builds rows via the helper (deps already injected).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/api/routers/soc.py` | Modified | `TicketItem` fields + `_enrich_ticket_item` |
| `tests/api/test_soc_router.py` or new | New | Smart-inbox enrichment tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Enrichment slows the list | Low | Rule-based + in-memory assess; ≤25 tickets |
| A malformed ticket breaks the list | Low | Per-ticket try/except, fields default to null |
| Existing tests break | Low | New fields are additive/optional |

## Rollback Plan
1. Revert `TicketItem` fields and `_enrich_ticket_item`
2. Restore the previous inline `TicketItem(...)` construction

## Dependencies
- **CE-02** (queue suggestion / rule path) and **SLA-04** (risk) — done.

## Success Criteria
- [ ] `GET /soc/tickets` rows include `slaRisk`, `suggestedQueue`, `owner`, `queue`
- [ ] Risk values are valid SLA risk levels for ticketed-with-SLA rows
- [ ] Suggested queue is a real queue slug
- [ ] Enrichment never breaks the list; existing queue tests keep passing
