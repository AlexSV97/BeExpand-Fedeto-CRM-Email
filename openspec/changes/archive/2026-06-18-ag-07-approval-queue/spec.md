# Agent Approval Queue — AG-07 Spec

## Purpose

Expose the queue of agent recommendations that require human approval and are
still pending a decision, so critical actions are reviewed before being applied
(human-in-the-loop).

## Requirements

### REQ-1: list_pending_approvals

`AgentGovernanceService` MUST expose `list_pending_approvals(db, limit=50)`
returning `OperationalRecord` rows with `record_kind="agent_recommendation"` and
`status="pending"`, ordered newest-first.

### REQ-2: Decided items leave the queue

When a recommendation is approved or rejected (`persist_approval`), its status
MUST change away from `"pending"` so it no longer appears in the queue.

### REQ-3: Auto-approved items are not pending

Recommendations that did not require approval (persisted with
`status="auto_approved"`) MUST NOT appear in the pending queue.

### REQ-4: Endpoint

`GET /agents/approvals/pending` MUST return the pending queue (serialized
records), require authentication, and accept a `limit` query parameter.

## Scenarios

### Scenario 1: A recommendation requiring approval appears as pending

- GIVEN a recommendation persisted with `status="pending"`
- WHEN `list_pending_approvals()` runs
- THEN that record is returned

### Scenario 2: Auto-approved recommendation is not pending

- GIVEN a recommendation persisted with `status="auto_approved"`
- WHEN `list_pending_approvals()` runs
- THEN that record is NOT returned

### Scenario 3: Approving removes from the queue

- GIVEN a pending recommendation
- WHEN it is approved via `persist_approval`
- THEN `list_pending_approvals()` no longer returns it

### Scenario 4: Endpoint returns the queue

- GIVEN an authenticated `GET /agents/approvals/pending`
- THEN the response is 200 with `items` and `total`

### Scenario 5: Endpoint requires auth

- GIVEN no auth header
- WHEN `GET /agents/approvals/pending` is called
- THEN the response is 401

## Non-functional Requirements

- **NFR-1 (No migration)**: reuse `OperationalRecord`.
- **NFR-2 (Consistent)**: ordering and serialization match `/agents/history`.

## Out of Scope

- Approval policy changes
- Pending notifications
