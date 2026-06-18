# External Escalation — CE-06 Spec

## Purpose

Hand off a ticket to an external destination (manufacturer / external ITSM) with
a persisted tracking reference, keeping the case traceable while it is worked
externally. Completes Épica 2 (queues & escalation).

## Requirements

### REQ-1: ExternalEscalationService

An `ExternalEscalationService` MUST accept an `AsyncSession` and a
`QueueStrategyService`, and expose `escalate(...)`, `list_for_ticket(...)` and
`to_item(...)`. Handoffs MUST persist as `OperationalRecord` rows with
`record_kind="external_escalation"`.

### REQ-2: Destination → special queue

The service MUST map the destination to a special queue slug:
`fabricante → special-fabricante`, `external_itsm → special-external-itsm`. The
target slug MUST exist among `QueueStrategyService.topology().special_queues`;
otherwise the service MUST raise a validation error.

### REQ-3: Tracking reference

`escalate()` MUST create an `ExternalRef` with `system` = destination,
`entity_type = "external_case"`, and `external_id` = the caller-provided id or a
generated one (destination-prefixed). The `ExternalRef` MUST be stored in the
record payload and returned in the result.

### REQ-4: Persisted handoff

The record MUST capture `resource_id` = ticket id, `actor_name`, `status="sent"`,
and a payload with destination, queue slug, tracking ref and reason.

### REQ-5: Endpoints

The system MUST expose, requiring authentication:
- `POST /soc/tickets/{id}/escalate-external` (body: destination, optional reason,
  optional external_id) returning the handoff result with the tracking ref
- `GET /soc/tickets/{id}/external-escalations` returning the handoff history

### REQ-6: Validation

An unknown destination MUST yield HTTP 422. Best-effort OTRS move to the special
queue MUST NOT break the endpoint on failure.

## Scenarios

### Scenario 1: Escalate to manufacturer resolves special queue

- GIVEN TICKET-1 and destination `fabricante`
- WHEN `escalate()` runs
- THEN the result `queue_slug == "special-fabricante"` and a tracking `ExternalRef` is returned

### Scenario 2: Tracking reference uses provided external id

- GIVEN destination `external_itsm` and `external_id="SNOW-123"`
- WHEN `escalate()` runs
- THEN `tracking_ref.external_id == "SNOW-123"` and `tracking_ref.system == "external_itsm"`

### Scenario 3: Tracking reference generated when not provided

- GIVEN destination `fabricante` and no `external_id`
- WHEN `escalate()` runs
- THEN `tracking_ref.external_id` is a non-empty generated value

### Scenario 4: Handoff persisted and listable

- GIVEN an external escalation recorded for TICKET-1
- WHEN `list_for_ticket("TICKET-1")` runs
- THEN it returns ≥1 record of kind `"external_escalation"`

### Scenario 5: Unknown destination rejected

- GIVEN destination `"nope"`
- WHEN `POST /soc/tickets/{id}/escalate-external` is called
- THEN the response is 422

### Scenario 6: Endpoint round-trip

- GIVEN `POST /soc/tickets/TICKET-1000/escalate-external {"destination":"fabricante"}`
- WHEN followed by `GET /soc/tickets/TICKET-1000/external-escalations`
- THEN the history has ≥1 item with `queue_slug == "special-fabricante"`

### Scenario 7: Endpoints require auth

- GIVEN no auth header
- WHEN any external-escalation endpoint is called
- THEN the response is 401

## Non-functional Requirements

- **NFR-1 (No migration)**: Reuse `OperationalRecord`.
- **NFR-2 (Best-effort)**: OTRS propagation never breaks the flow.
- **NFR-3 (Isolation)**: `"external_escalation"` records MUST NOT appear in the
  existing audit / recommendation / escalation / ownership queries.

## Out of Scope

- Real vendor/ITSM API delivery and status callbacks
- Idempotency / dedup of handoffs
