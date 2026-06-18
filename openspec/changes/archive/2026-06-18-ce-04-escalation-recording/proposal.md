# Proposal: CE-04 — Registro de escalados

## Intent

CE-03 computes escalation plans but persistence is limited to a generic
`audit_event` row with the action string `"ticket.escalated"`. There is no
dedicated, queryable escalation history per ticket. This adds first-class
escalation recording: each escalation is persisted as a structured record and
exposed through a history endpoint.

## Scope

### In Scope
- `EscalationRecordService`: persist an escalation to `OperationalRecord`
  (`record_kind="escalation"`) and query it (per ticket / global)
- Record the full `EscalationPlan` (from/to tier, queue, level, steps, reason)
- Wire the SOC escalate endpoint to record each escalation
- `GET /soc/tickets/{ticket_id}/escalations` history endpoint
- Unit + endpoint tests

### Out of Scope
- New DB table / migration (reuse `OperationalRecord`, like the other records)
- Editing / deleting escalation records
- SLA-timer-triggered escalation
- Frontend UI

## Capabilities

### New Capabilities
- `escalation-recording`: persisted, queryable escalation history

### Modified Capabilities
- none (the SOC escalate endpoint gains a recording side-effect; response shape
  unchanged)

## Approach
1. `EscalationRecordService(db)` with `record(...)`, `list_for_ticket(...)`,
   `list_all(...)` backed by `OperationalRecord` rows of kind `"escalation"`.
2. The SOC escalate endpoint records the computed `EscalationPlan` after acting.
3. `GET /soc/tickets/{ticket_id}/escalations` returns the serialized history.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/escalation_recording.py` | New | `EscalationRecordService` + API models |
| `src/api/routers/soc.py` | Modified | record on escalate; history endpoint |
| `tests/test_escalation_recording.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Recording failure blocks escalation | Medium | Best-effort: never raise out of the escalate flow |
| New record_kind pollutes existing history queries | Low | Existing queries filter explicit kinds; `"escalation"` is excluded |
| Payload schema drift | Low | Store `EscalationPlan.model_dump(mode="json")` verbatim |

## Rollback Plan
1. Remove the history endpoint and the recording call in the SOC escalate endpoint
2. Delete `EscalationRecordService`
3. No schema changes (records remain as inert `OperationalRecord` rows)

## Dependencies
- **CE-03** (EscalationService / EscalationPlan) — done.

## Success Criteria
- [ ] Each escalation persists an `OperationalRecord` of kind `"escalation"`
- [ ] `list_for_ticket()` returns a ticket's escalations newest-first
- [ ] `GET /soc/tickets/{id}/escalations` returns the serialized history
- [ ] Recording never breaks the escalate flow
- [ ] Existing SOC escalate + audit tests keep passing
