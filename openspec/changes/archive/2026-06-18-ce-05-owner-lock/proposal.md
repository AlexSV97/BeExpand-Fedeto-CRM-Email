# Proposal: CE-05 — Gestión de owner/lock por ticket

## Intent

Backlog story CE-05 (Épica 2): "El ticket tiene propietario y bloqueo
rastreables". Today ownership only exists as static fields on the mock tickets
(`owner`, `assigned_to`) with no way to assign, lock/unlock, query or audit it.
This adds trackable ownership and locking, persisted and exposed via the SOC API,
with best-effort propagation to OTRS.

## Scope

### In Scope
- `TicketOwnershipService`: assign owner, lock, unlock; derive current state;
  history — persisted as `OperationalRecord` (`record_kind="ownership"`)
- Each change stores a full state snapshot `{owner, locked, locked_by}`
- SOC endpoints: assign / lock / unlock / get ownership (state + history)
- Best-effort OTRS `update_ticket(owner=...)` on assign
- Unit + endpoint tests

### Out of Scope
- New DB table / migration (reuse `OperationalRecord`)
- Concurrency/locking enforcement across requests (advisory lock state only)
- Tenant/RBAC ownership rules (handled by existing auth)
- Frontend

## Capabilities

### New Capabilities
- `ticket-ownership`: trackable owner + lock state with history

### Modified Capabilities
- none (additive endpoints)

## Approach
1. `TicketOwnershipService(db)` with `assign`, `lock`, `unlock`,
   `current_state`, `list_history`.
2. Compute new state from previous + action; persist snapshot in the record payload.
3. SOC endpoints record the change and (on assign) propagate owner to OTRS best-effort.
4. `GET /soc/tickets/{id}/ownership` returns current state + history.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/ticket_ownership.py` | New | `TicketOwnershipService` + models |
| `src/api/routers/soc.py` | Modified | assign/lock/unlock + ownership endpoints |
| `tests/test_ticket_ownership.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OTRS propagation fails | Medium | Best-effort: never raise out of the endpoint |
| Lock not enforced (advisory) | Accepted | Documented; enforcement is out of scope |
| State drift if records hand-edited | Low | Snapshot-per-record; latest wins |

## Rollback Plan
1. Remove the ownership endpoints
2. Delete `TicketOwnershipService`
3. No schema changes (records remain inert)

## Dependencies
- **BT-05** (RBAC/tenant context) — existing auth; **CE-01** topology unaffected.

## Success Criteria
- [ ] Assigning an owner persists an `ownership` record and updates current state
- [ ] Lock/unlock toggles `locked` with `locked_by`
- [ ] `current_state()` reflects the latest change
- [ ] `GET /soc/tickets/{id}/ownership` returns state + history
- [ ] Endpoints never break on OTRS failure; existing tests keep passing
