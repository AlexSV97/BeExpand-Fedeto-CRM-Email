# Proposal: CE-01 — Modelar árbol de colas

## Intent

Two inconsistent queue topologies: `ActionExecutor.QUEUE_MAP` (3 entries, ticket creation) vs `QueueStrategyService._topology` (6 entries, routing recommendations). Neither persisted, neither validated against OTRS. This creates a single DB-backed hierarchy with parent-child relationships, synced from OTRS.

## Scope

### In Scope
- `queues` DB table with self-referencing `parent_id` FK
- Domain `Queue` model: add `parent_id`
- `QueueSyncService`: sync from OTRS `list_queues()`
- `QueueStrategyService`: load from DB
- `ActionExecutor._resolve_queue()`: validate against DB
- Alembic migration + seed data (N1/N2/N3 + specials)
- Unit tests

### Out of Scope
- Queue CRUD UI, AI suggestions (CE-02), N-level escalation (CE-03), OTRS webhooks

## Capabilities

### New Capabilities
- `queue-topology`: Persisted queue hierarchy with OTRS sync

### Modified Capabilities
- `queue-routing-strategy`: Load from DB; validate before ticket creation

## Approach
1. `QueueModel` ORM: id, name, slug, parent_id (self-ref FK), tier, owner, is_active, external_id, metadata
2. Add `parent_id: str | None` to domain `Queue`
3. `QueueSyncService`: upsert from OTRS; seed fallback if unreachable
4. `QueueStrategyService`: accept `AsyncSession`, load from DB, fallback to hardcoded
5. `ActionExecutor._resolve_queue()`: query DB, raise if missing
6. Alembic migration + tests

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/db/models.py` | Modified | Add `QueueModel` |
| `src/domain/ticketing.py` | Modified | Add `parent_id` |
| `src/services/queue_strategy.py` | Modified | Load from DB |
| `src/agents/action_executor.py` | Modified | Validate queue |
| `src/services/queue_sync.py` | New | Sync service |
| `alembic/versions/` | New | Migration |
| `tests/` | Modified | New + adapt existing |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OTRS no parent_id in API | High | Convention-based mapping from name prefixes; seed known topology |
| Migration conflicts | Low | New table only |
| Sync blocks ticket creation | Low | Fail-open: fallback to hardcoded |

## Rollback Plan
1. `alembic downgrade -1`
2. Revert `QueueStrategyService` to hardcoded
3. Revert `ActionExecutor._resolve_queue()` to QUEUE_MAP
4. Delete `QueueSyncService`

## Dependencies
- **BT-02** (canonical model) — done.

## Success Criteria
- [ ] `queues` table with self-referencing FK via migration
- [ ] `QueueStrategyService.topology()` returns DB-backed data
- [ ] `ActionExecutor` validates queue exists in DB
- [ ] `QueueSyncService` produces consistent tree from OTRS
- [ ] All existing tests pass with DB-backed topology
- [ ] Seed data produces correct N1/N2/N3 + special topology
