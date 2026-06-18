# Proposal: CE-06 — Escalado a fabricante / ITSM externo

## Intent

Backlog story CE-06 (Épica 2): "Se puede enviar el caso a un destino externo con
tracking". Close the queue/escalation epic by routing a ticket to an external
destination (manufacturer / external ITSM), creating a **tracking reference** and
persisting the handoff, so the case stays traceable while owned externally.

## Scope

### In Scope
- `ExternalEscalationService`: route a ticket to a special queue
  (`special-fabricante` / `special-external-itsm`), mint an `ExternalRef`
  tracking reference, and persist the handoff (`record_kind="external_escalation"`)
- Validate the destination resolves to an existing special queue (CE-01 topology)
- `POST /soc/tickets/{id}/escalate-external` + `GET /soc/tickets/{id}/external-escalations`
- Best-effort OTRS move to the special queue
- Unit + endpoint tests

### Out of Scope
- Real API integration with a specific manufacturer/ITSM vendor (the tracking ref
  is recorded; outbound delivery is a future integration)
- New DB table / migration (reuse `OperationalRecord`)
- Bidirectional sync / status callbacks from the external system

## Capabilities

### New Capabilities
- `external-escalation`: hand off a ticket to an external destination with a
  persisted tracking reference

### Modified Capabilities
- none (additive endpoints)

## Approach
1. Map destination (`fabricante` | `external_itsm`) → special queue slug.
2. Validate the slug exists among `QueueStrategyService.topology().special_queues`.
3. Build an `ExternalRef(system=<destination>, entity_type="external_case",
   external_id=<provided|generated>)`.
4. Persist an `external_escalation` `OperationalRecord` with the destination,
   queue and tracking ref.
5. Endpoint records the handoff and best-effort moves the OTRS ticket to the queue.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/external_escalation.py` | New | Service + models |
| `src/api/routers/soc.py` | Modified | escalate-external + history endpoints |
| `tests/test_external_escalation.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Unknown destination | Medium | Validated enum → 422 |
| Special queue missing in topology | Low | Validate vs topology → 400 |
| OTRS move fails | Medium | Best-effort: never raise |
| Duplicate handoffs | Low | Each call records a new tracked handoff; idempotency out of scope |

## Rollback Plan
1. Remove the external-escalation endpoints
2. Delete `ExternalEscalationService`
3. No schema changes

## Dependencies
- **CE-01** (special queues), **CE-04** (recording pattern), `ExternalRef` domain — done.

## Success Criteria
- [ ] Escalating to `fabricante`/`external_itsm` resolves the right special queue
- [ ] A tracking `ExternalRef` is created and persisted
- [ ] Handoff persisted as `external_escalation` and listable per ticket
- [ ] Unknown destination → 422; OTRS failure never breaks the flow
- [ ] Completes Épica 2 (CE-01..CE-06)
