# Ticket Ownership & Lock — CE-05 Spec

## Purpose

Make ticket ownership and locking trackable: assign an owner, lock/unlock a
ticket, query the current ownership state, and audit the full change history.

## Requirements

### REQ-1: TicketOwnershipService

A `TicketOwnershipService` MUST accept an `AsyncSession` and expose `assign`,
`lock`, `unlock`, `current_state` and `list_history`. Changes MUST persist as
`OperationalRecord` rows with `record_kind="ownership"`.

### REQ-2: State snapshot per change

Each change MUST store, in the record payload, the resulting state
`{owner, locked, locked_by}` plus the `action` and `actor`. `current_state()` MUST
return the snapshot of the most recent record (or an empty default if none).

### REQ-3: Assign sets owner

`assign(ticket_id, owner, actor_name)` MUST set the owner, preserving the current
lock state, and persist an `action="assign"` record.

### REQ-4: Lock and unlock

`lock(ticket_id, actor_name)` MUST set `locked=True` and `locked_by=actor_name`,
keeping the existing owner (or defaulting it to the actor). `unlock(...)` MUST set
`locked=False` and clear `locked_by`, keeping the owner.

### REQ-5: History

`list_history(ticket_id, limit)` MUST return only `"ownership"` records for that
ticket, newest-first.

### REQ-6: SOC endpoints

The system MUST expose, all requiring authentication:
- `POST /soc/tickets/{id}/assign` (body: owner, optional reason)
- `POST /soc/tickets/{id}/lock`
- `POST /soc/tickets/{id}/unlock`
- `GET /soc/tickets/{id}/ownership` (current state + history)

### REQ-7: Best-effort OTRS propagation

On assign, the endpoint SHOULD propagate the owner to OTRS via `update_ticket`.
Propagation MUST be best-effort: a failure MUST NOT change the response or raise.

## Scenarios

### Scenario 1: Assign sets owner

- GIVEN TICKET-1 with no ownership records
- WHEN `assign("TICKET-1", "alice", "admin")` runs
- THEN `current_state("TICKET-1").owner == "alice"` and a record of kind `"ownership"` exists

### Scenario 2: Lock sets locked + locked_by

- GIVEN TICKET-1 owned by alice
- WHEN `lock("TICKET-1", "bob")` runs
- THEN current state has `locked=True`, `locked_by="bob"`, `owner` preserved

### Scenario 3: Unlock clears lock, keeps owner

- GIVEN TICKET-1 locked by bob, owner alice
- WHEN `unlock("TICKET-1", "bob")` runs
- THEN current state has `locked=False`, `locked_by=None`, `owner="alice"`

### Scenario 4: Current state is the latest change

- GIVEN assign→lock→unlock for TICKET-1
- WHEN `current_state` runs
- THEN it reflects the unlock (latest)

### Scenario 5: Empty default for unknown ticket

- GIVEN no records for TICKET-9
- WHEN `current_state("TICKET-9")` runs
- THEN it returns `owner=None, locked=False, locked_by=None`

### Scenario 6: Assign endpoint round-trips

- GIVEN `POST /soc/tickets/TICKET-1000/assign {"owner":"alice"}`
- WHEN followed by `GET /soc/tickets/TICKET-1000/ownership`
- THEN the response state has `owner="alice"` and history length ≥ 1

### Scenario 7: Endpoints require auth

- GIVEN no auth header
- WHEN any ownership endpoint is called
- THEN the response is 401

## Non-functional Requirements

- **NFR-1 (No migration)**: Reuse `OperationalRecord`.
- **NFR-2 (Best-effort side-effects)**: OTRS propagation never breaks the flow.
- **NFR-3 (Isolation)**: `"ownership"` records MUST NOT appear in existing audit /
  recommendation / escalation queries.

## Out of Scope

- Enforced (blocking) locks across concurrent requests
- Dedicated ownership table
