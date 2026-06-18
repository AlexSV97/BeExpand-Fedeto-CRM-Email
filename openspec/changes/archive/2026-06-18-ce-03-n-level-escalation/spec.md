# N-Level Escalation — CE-03 Spec

## Purpose

Provide hierarchy-aware, multi-level ticket escalation over the persisted queue
topology (CE-01). Escalation moves a ticket up the tier chain (N1→N2→N3),
either to an explicitly requested tier or automatically to the next level,
returning the full path traversed.

## Requirements

### REQ-1: EscalationService

An `EscalationService` MUST accept a `QueueStrategyService` and expose
`escalate(request) -> EscalationPlan`. The method MUST NOT raise; invalid or
no-op inputs MUST return a plan with `should_escalate=False`.

### REQ-2: Tier chain from topology

The escalation chain MUST be derived from `strategy.topology()`, ordered by tier
rank (n1 < n2 < n3 < special). The service MUST NOT hardcode the chain.

### REQ-3: Resolve current tier

If `current_queue_slug` is provided, the current tier MUST be resolved by looking
the slug up in the topology. Otherwise `current_tier` MUST be used. An unknown
slug MUST default to N1.

### REQ-4: Auto next-level escalation

When no `target_tier` is given, the service MUST escalate to the next tier up
(current rank + 1). If the current tier is already the highest chain tier, the
plan MUST have `should_escalate=False`.

### REQ-5: Explicit target tier

When `target_tier` is given, it MUST be honored if its rank is higher than the
current tier. If its rank is lower than or equal to the current tier, the plan
MUST have `should_escalate=False` and leave the ticket on its current tier.

### REQ-6: Multi-level path

`EscalationPlan.steps` MUST list every tier traversed from current+1 up to the
target (inclusive), each with its queue and level, so a jump such as N1→N3
yields two steps (N2, N3).

### REQ-7: Escalation endpoint

The system MUST expose `POST /queues/escalate` accepting an `EscalationRequest`
and returning an `EscalationPlan`, requiring authentication.

### REQ-8: SOC escalate uses the service

The SOC `POST /soc/tickets/{id}/escalate` endpoint MUST compute its
`escalation_level` and `target_queue` from `EscalationService`, using the
ticket's real queue as the current tier and honoring the request `target_tier`.
Its response shape MUST be unchanged.

## Scenarios

### Scenario 1: Auto escalation goes one level up

- GIVEN a ticket on tier N1
- WHEN `escalate()` runs with no target tier
- THEN `should_escalate` is true, `to_tier` is N2 and `level` is 2

### Scenario 2: Explicit target tier honored

- GIVEN a ticket on tier N1 and `target_tier=n3`
- WHEN `escalate()` runs
- THEN `to_tier` is N3, `level` is 3 and `steps` are [N2, N3]

### Scenario 3: Target not higher than current is a no-op

- GIVEN a ticket on tier N2 and `target_tier=n1`
- WHEN `escalate()` runs
- THEN `should_escalate` is false and `to_tier` is N2

### Scenario 4: Already at the top tier

- GIVEN a ticket on tier N3 with no target tier
- WHEN `escalate()` runs
- THEN `should_escalate` is false

### Scenario 5: Current tier resolved from queue slug

- GIVEN `current_queue_slug="n2-resolucion"` and no explicit `current_tier`
- WHEN `escalate()` runs with no target tier
- THEN `from_tier` is N2 and `to_tier` is N3

### Scenario 6: Endpoint returns serialized plan

- GIVEN an authenticated `POST /queues/escalate` with a valid request
- THEN the response is 200 with an `EscalationPlan` (should_escalate, from/to, level, steps)

### Scenario 7: SOC escalate keeps its contract

- GIVEN `POST /soc/tickets/TICKET-1000/escalate` with `target_tier=n2`
- THEN the response is 200 with `status="escalated"`, `escalation_level` and `target_queue`

## Non-functional Requirements

- **NFR-1 (Pure logic)**: `escalate()` performs no I/O; topology is provided by
  the injected `QueueStrategyService`.
- **NFR-2 (Backward compatible)**: The SOC escalate response shape and all its
  existing tests MUST keep passing.

## Out of Scope

- Escalation history persistence (CE-04)
- SLA-timer-triggered automatic escalation
