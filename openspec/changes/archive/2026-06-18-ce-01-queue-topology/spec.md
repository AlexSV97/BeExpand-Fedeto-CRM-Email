# Queue Topology — CE-01 Spec

## Purpose

Two hardcoded, inconsistent queue topologies exist today: `ActionExecutor.QUEUE_MAP` (3 entries, for ticket creation) and `QueueStrategyService._topology` (6 entries, for routing recommendations). Neither is persisted nor validated against OTRS. This change introduces a single DB-backed queue hierarchy with parent-child relationships, synced from OTRS with seed fallback, as the canonical source of truth.

## Requirements

### REQ-1: Queue Table with Hierarchy

The system MUST provide a `queues` table with these columns: `id`, `name`, `slug`, `parent_id` (self-referencing FK to `id`), `tier`, `owner`, `is_active`, `external_id`, `metadata`.

### REQ-2: QueueSyncService

A `QueueSyncService` SHALL sync queues from OTRS `list_queues()` into the local `queues` table via upsert. If OTRS is unreachable, the service MUST seed the table with the known topology.

### REQ-3: QueueStrategyService loads Topology from DB

`QueueStrategyService.topology()` MUST load nodes from the `queues` table instead of the hardcoded `self._topology`. The class MAY accept an `AsyncSession` dependency for DB access.

### REQ-4: ActionExecutor validates resolved queue

`ActionExecutor._resolve_queue()` MUST verify the resolved queue name exists as an active row in the `queues` table. If it does not, the system MUST fall back to `OtrsZnunySettings.default_queue`.

### REQ-5: Seed data for known topology

The system MUST seed these queues on first sync or as OTRS fallback: N1 - Triage (tier=n1), N2 - Resolucion (tier=n2), N3 - Ingenieria (tier=n3), Special - Fabricante, Special - External ITSM, Special - Seguridad (tier=special). Parent-child relationships MUST reflect the operational N1 to N2 to N3 escalation chain.

### REQ-6: Domain Queue model gets parent_id

The domain `Queue` model in `src/domain/ticketing.py` MUST add `parent_id: str | None`, `tier: str | None`, and `owner: str | None` fields.

## Scenarios

### Scenario 1: Queue hierarchy loads from DB with correct parent-child

- GIVEN the `queues` table has N1 to N2 to N3 parent-child relationships
- WHEN `QueueStrategyService.topology()` is called
- THEN it returns a `QueueTopology` whose roots and children match the DB rows and `parent_id` links

### Scenario 2: Queue sync from OTRS creates and updates local records

- GIVEN OTRS `list_queues()` returns queues with names "N1 - Triage", "N2 - Resolucion"
- WHEN `QueueSyncService.sync()` runs
- THEN the `queues` table contains rows with matching names, external_ids, and correct `parent_id`

### Scenario 3: OTRS unavailable = falls back to seeded topology

- GIVEN OTRS is unreachable (connection error or health check fails)
- WHEN `QueueSyncService.sync()` is called
- THEN the `queues` table is populated with the 6 seed rows (3 N-tier + 3 specials)

### Scenario 4: ActionExecutor resolves queue and validates against DB

- GIVEN `_resolve_queue()` returns `Queue(name="Support")`
- WHEN the resolved queue is validated against the DB
- THEN the system checks "Support" exists and is active in the `queues` table
- AND succeeds if found

### Scenario 5: QueueStrategyService recommends queue based on DB topology

- GIVEN `QueueStrategyService` is initialized with a DB session containing active N1/N2/N3 rows
- WHEN `recommend()` routes a ticket to N2
- THEN `decision.routing.queue` has a `name` matching the DB row for N2 - Resolucion

### Scenario 6: Unknown queue name = fallback to default

- GIVEN `_resolve_queue()` resolves to "NonExistentQueue" which is absent from the `queues` table
- WHEN validation runs
- THEN the system falls back to `OtrsZnunySettings.default_queue` ("Support")

## Non-functional Requirements

- **NFR-1 (Backward compatible)**: All existing queue resolution and recommendation behavior MUST be preserved. `QUEUE_MAP` and `DEPARTMENT_QUEUE_MAP` MAY remain as fallback mappings during migration.
- **NFR-2 (Idempotent sync)**: Running `QueueSyncService.sync()` multiple times with the same OTRS data MUST produce the same `queues` table state (upsert, not duplicate).

## Out of Scope

- Queue management UI (CRUD) — skipped intentionally
- Queue suggestion AI (CE-02) — separate change
- N-level escalation (CE-03) — separate change
- Escalation recording (CE-04) — separate change

