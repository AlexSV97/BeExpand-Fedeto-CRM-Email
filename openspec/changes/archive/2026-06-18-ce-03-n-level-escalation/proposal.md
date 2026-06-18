# Proposal: CE-03 — Escalado N-niveles

## Intent

Escalation today is keyword-driven: the SOC escalate endpoint hardcodes
`current_tier=N1` and derives a target tier from `QueueStrategyService.recommend()`,
ignoring the ticket's real tier, the requested `target_tier`, and the persisted
queue hierarchy (CE-01). This adds hierarchy-aware, multi-level escalation that
computes the escalation path over the DB topology tier chain (N1→N2→N3 +
specials), honoring an explicit target tier or auto-selecting the next level up.

## Scope

### In Scope
- `EscalationService`: compute an `EscalationPlan` from current tier/queue over
  the topology tier chain
- Auto next-level escalation and explicit `target_tier`
- Multi-level path (`steps`) when jumping more than one level (e.g. N1→N3)
- `POST /queues/escalate` endpoint
- Wire the SOC escalate endpoint to use the service (real current tier from the
  ticket's queue; honor `target_tier`)
- Unit + endpoint tests

### Out of Scope
- Persisting escalation history / audit beyond what the SOC endpoint already logs
  (escalation **recording** is CE-04)
- Auto-triggered escalation by SLA timers
- Re-modelling the seed parent links (N1/N2/N3 remain roots; chain is by tier rank)

## Capabilities

### New Capabilities
- `queue-escalation`: N-level escalation over the persisted topology

### Modified Capabilities
- none (the SOC escalate endpoint is rewired to the new service; response shape
  unchanged)

## Approach
1. `EscalationService(strategy)` builds the tier chain from `strategy.topology()`.
2. Resolve current tier from `current_queue_slug` (or explicit `current_tier`).
3. Target = explicit `target_tier` (must be higher rank) or current rank + 1.
4. Produce `EscalationPlan(should_escalate, from/to tier+queue, level, steps, reason)`.
5. Expose `POST /queues/escalate`; rewire SOC `escalate` to set
   `escalation_level`/`target_queue` from the plan.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/escalation.py` | New | `EscalationService` + models |
| `src/api/routers/queues.py` | Modified | `POST /queues/escalate` |
| `src/api/routers/soc.py` | Modified | escalate endpoint uses the service |
| `tests/test_escalation.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Breaking existing SOC escalate tests | Medium | Preserve response shape; tests only assert 200 + fields |
| Target tier not higher than current | Medium | `should_escalate=False`, return current as no-op |
| Unknown current queue slug | Low | Default to N1 |
| Escalating from top tier (N3) | Low | `should_escalate=False` |

## Rollback Plan
1. Revert SOC escalate endpoint to the previous keyword-based derivation
2. Remove `POST /queues/escalate`
3. Delete `EscalationService`
4. No schema changes

## Dependencies
- **CE-01** (DB-backed topology) — done.

## Success Criteria
- [ ] `EscalationService.escalate()` returns the next tier up by default
- [ ] Explicit `target_tier` honored; lower/equal target → no escalation
- [ ] Multi-level jump produces an intermediate `steps` path
- [ ] `POST /queues/escalate` returns the serialized plan
- [ ] SOC escalate endpoint keeps its response shape and all its tests pass
