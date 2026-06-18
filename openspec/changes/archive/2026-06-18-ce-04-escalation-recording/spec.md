# Escalation Recording — CE-04 Spec

## Purpose

Persist each ticket escalation as a structured, queryable record and expose a
per-ticket escalation history, building on the `EscalationPlan` from CE-03.

## Requirements

### REQ-1: EscalationRecordService

An `EscalationRecordService` MUST accept an `AsyncSession` and expose
`record(...)`, `list_for_ticket(...)` and `list_all(...)`. Records MUST be stored
as `OperationalRecord` rows with `record_kind="escalation"`.

### REQ-2: Record content

`record()` MUST persist: `resource_id` = ticket id, `actor_name`, a `status`
(`"escalated"` when `plan.should_escalate` else `"noop"`), a human title, and a
`payload` containing the full `EscalationPlan` (from/to tier, from/to queue,
level, steps, reason).

### REQ-3: Per-ticket history

`list_for_ticket(ticket_id)` MUST return only `"escalation"` records for that
ticket, ordered newest-first, limited by a `limit` argument.

### REQ-4: SOC escalate records the escalation

`POST /soc/tickets/{id}/escalate` MUST persist an escalation record via
`EscalationRecordService` using the computed plan. Recording MUST be best-effort:
a recording failure MUST NOT change the endpoint's response or raise.

### REQ-5: History endpoint

The system MUST expose `GET /soc/tickets/{ticket_id}/escalations` returning the
ticket's escalation history (serialized), requiring authentication.

### REQ-6: Isolation from other record kinds

Recording escalations MUST NOT appear in the existing `audit_event`,
`agent_recommendation` or `agent_approval` queries (those filter explicit kinds).

## Scenarios

### Scenario 1: Recording persists an escalation row

- GIVEN an `EscalationPlan` from N1 to N2 for TICKET-1
- WHEN `record()` is called
- THEN an `OperationalRecord` with `record_kind="escalation"`, `resource_id="TICKET-1"`
  and `status="escalated"` exists

### Scenario 2: No-op plan recorded with noop status

- GIVEN an `EscalationPlan` with `should_escalate=False`
- WHEN `record()` is called
- THEN the persisted record has `status="noop"`

### Scenario 3: Per-ticket history newest-first

- GIVEN two escalations recorded for TICKET-1
- WHEN `list_for_ticket("TICKET-1")` runs
- THEN it returns 2 records, the most recent first

### Scenario 4: History is ticket-scoped

- GIVEN escalations for TICKET-1 and TICKET-2
- WHEN `list_for_ticket("TICKET-1")` runs
- THEN only TICKET-1 records are returned

### Scenario 5: SOC escalate creates a record

- GIVEN `POST /soc/tickets/TICKET-1000/escalate` with a valid reason
- WHEN it succeeds
- THEN a subsequent `GET /soc/tickets/TICKET-1000/escalations` returns at least one item

### Scenario 6: History endpoint requires auth

- GIVEN no auth header
- WHEN `GET /soc/tickets/TICKET-1000/escalations` is called
- THEN the response is 401

### Scenario 7: Recording failure does not break escalate

- GIVEN recording raises internally
- WHEN `POST /soc/tickets/{id}/escalate` runs
- THEN the response is still 200 with `status="escalated"`

## Non-functional Requirements

- **NFR-1 (No migration)**: Reuse `OperationalRecord`; no schema change.
- **NFR-2 (Best-effort)**: Recording side-effects MUST never break escalation.

## Out of Scope

- Dedicated escalation table
- Editing/deleting records
- Frontend
