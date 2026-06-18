# Smart Inbox — CP-01 Spec

## Purpose

Enrich the ticket queue so each row shows, at a glance, the operational context an
analyst needs to triage: priority, SLA risk, suggested queue and owner.

## Requirements

### REQ-1: Enriched TicketItem

`TicketItem` (rows of `GET /soc/tickets`) MUST include, in addition to the
existing fields: `owner`, `queue`, `slaRisk`, `slaRemainingMinutes`,
`suggestedQueue`. The new fields MUST be optional (nullable).

### REQ-2: SLA risk from lifecycle

For a ticket with an SLA, `slaRisk` MUST be its `TicketLifecycleService` risk
level (`low|watch|high|critical`) and `slaRemainingMinutes` the remaining budget.
For a ticket without an SLA, both MUST be null.

### REQ-3: Suggested queue from rules

`suggestedQueue` MUST be the slug recommended by `QueueStrategyService.recommend`
(rule-based, no LLM) for the ticket. It MUST be a slug that exists in the topology.

### REQ-4: Owner and queue

`owner` MUST reflect the ticket owner and `queue` the current queue slug.

### REQ-5: Resilient enrichment

Computing the enriched fields MUST NOT break the list: a per-ticket failure MUST
leave the offending fields null and still return the row.

### REQ-6: Backward compatible

Existing fields and filtering/pagination behavior MUST be unchanged.

## Scenarios

### Scenario 1: Rows carry SLA risk and suggested queue

- GIVEN authenticated `GET /soc/tickets`
- WHEN the response is returned
- THEN each row has a `slaRisk` in {low,watch,high,critical} and a non-empty `suggestedQueue`

### Scenario 2: Suggested queue is a real slug

- GIVEN a returned row
- THEN its `suggestedQueue` matches a queue slug from the topology (e.g. n1-triage/n2-resolucion/n3-ingenieria)

### Scenario 3: Owner present

- GIVEN tickets with owners
- THEN at least one row exposes a non-null `owner`

### Scenario 4: Existing behavior preserved

- GIVEN `GET /soc/tickets?priority=high`
- THEN filtering still works and rows still expose id/subject/status/priority

### Scenario 5: Enrichment is resilient

- GIVEN a ticket whose enrichment raises internally
- WHEN the list is built
- THEN the row is still returned with null enriched fields

## Non-functional Requirements

- **NFR-1 (Low latency)**: Enrichment is in-memory + rule-based; no per-row LLM/DB
  round-trips beyond the existing query.
- **NFR-2 (Additive)**: New fields are optional; no breaking change to consumers.

## Out of Scope

- LLM suggestion per row (CE-02 endpoint)
- Sorting/filtering by the new fields
