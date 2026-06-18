# Design: CE-01 — Modelar árbol de colas

## Technical Approach

Replace two inconsistent hardcoded queue topologies (`QueueStrategyService._topology` with 6 nodes and `ActionExecutor.QUEUE_MAP`/`DEPARTMENT_QUEUE_MAP` with 3+6 entries) with a single `queues` DB table backed by a self-referencing foreign key. Introduce `QueueSyncService` to sync from OTRS while seeded fallback guarantees availability. Refactor consumers to load from DB, preserving backward compatibility.

## Architecture Decisions

### Decision: Self-referencing FK vs separate edge table

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Self-ref FK (`parent_id`) | Simple queries, single table, depth-limited by FK constraints | **Chosen** — tree is shallow (max 2 levels); avoids join table overhead |
| Adjacency list (edge table) | Supports arbitrary depth, cleaner DAG | Over-engineered for N1/N2/N3 + specials topology |

### Decision: Seed data strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Alembic `op.bulk_insert` in migration | Guaranteed present after `alembic upgrade`; couples data to schema version | **Chosen** — the topology IS schema, not runtime data |
| Standalone seed script | Easy to re-run; can be forgotten | Rejected — no guarantee topology exists in all environments |

### Decision: QueueStrategyService loads from DB async, falls back sync

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Accept `AsyncSession` in constructor, load eagerly | Forces async init; breaks existing tests | **Chosen** with twist: `__init__` accepts optional `QueueTopology`, a new async factory `create()` does the DB load |
| Make all methods async | Propagates async through routing logic (sync, no I/O) | Rejected — routing itself is pure logic, only topology source changes |

### Decision: ActionExecutor resolves via DB query vs cache

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Query `QueueModel` each call | Always consistent; small overhead (1 query per ticket) | **Chosen** — ticket creation is infrequent; consistency beats speed |
| Load topology once and cache in-memory | Stale if OTRS adds queues between calls | Rejected — simplicity > premature optimization for MVP |

## Data Flow

```
OTRS Znuny API                     DB (queues table)               Consumers
┌──────────────┐    sync_from_otrs()   ┌────────────┐   topology()   ┌──────────────────┐
│ list_queues() │ ──────────────────→  │ QueueModel │ ←──────────── │ QueueStrategySvc │
└──────────────┘                      │  (seeded)  │               └──────────────────┘
                                      │            │   _resolve_q()  ┌──────────────────┐
                                      │ parent_id──│←────────────── │ ActionExecutor   │
                                      └────────────┘               └──────────────────┘
                                           │
                                    alembic upgrade()
                                    (seed 11 rows)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/db/models.py` | Modify | Add `QueueModel` with self-ref FK |
| `src/domain/ticketing.py` | Modify | Add `parent_id: str \| None` to `Queue` |
| `src/services/queue_sync.py` | Create | `QueueSyncService` — sync, get_topology, get_by_name, ensure_seeded |
| `src/services/queue_strategy.py` | Modify | Accept optional `QueueTopology` in `__init__`; add async `create()` factory |
| `src/agents/action_executor.py` | Modify | Make `_resolve_queue()` async; query `QueueModel` via `self.db`; remove class-level QUEUE_MAP/DEPARTMENT_QUEUE_MAP |
| `src/api/routers/queues.py` | Modify | Wire `QueueSyncService` in `get_queue_strategy_service` dependency |
| `alembic/versions/` | Create | Migration: create `queues` table + seed 11 rows |
| `tests/test_queue_strategy.py` | Modify | Add DB-backed tests; existing tests keep working (backward compat) |
| `tests/test_queue_sync.py` | Create | Unit tests for sync, topology, fallback |
| `tests/test_action_executor.py` | Modify | Add tests for DB-backed queue resolution |

## Interfaces / Contracts

### QueueModel (src/db/models.py)

```python
class QueueModel(Base):
    __tablename__ = "queues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]]
    tier: Mapped[Optional[str]]  # "n1", "n2", "n3", "special", null
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("queues.id"), nullable=True)
    parent: Mapped[Optional["QueueModel"]] = relationship("QueueModel", remote_side="QueueModel.id", backref="children")
    otrs_external_id: Mapped[Optional[str]]
    is_active: Mapped[bool] = mapped_column(default=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
```

### QueueSyncService interface

```python
class QueueSyncService:
    def __init__(self, db: AsyncSession, otrs_client: OtrsZnunyClient | None = None)

    async def sync_from_otrs(self) -> int          # returns upserted count
    async def get_topology(self) -> QueueTopology    # builds tree from DB
    async def get_by_name(self, name: str) -> QueueModel | None
    async def ensure_seeded(self) -> None            # inserts seed data if table empty
```

### Domain Queue update

```python
class Queue(BaseModel):
    ...
    parent_id: str | None = None   # NEW — slug of parent queue
```

### Seed data (11 rows)

| name | slug | tier | parent |
|------|------|------|--------|
| N1 - Triage | n1-triage | n1 | null |
| N2 - Resolución | n2-resolucion | n2 | null |
| N3 - Ingeniería | n3-ingenieria | n3 | null |
| Special - Fabricante | special-fabricante | special | n3-ingenieria |
| Special - External ITSM | special-external-itsm | special | n3-ingenieria |
| Special - Seguridad | special-seguridad | special | n2-resolucion |
| Support | support | null | null |
| Ventas | ventas | null | null |
| Proveedores | proveedores | null | null |
| Contabilidad | contabilidad | null | null |
| Direccion | direccion | null | null |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `QueueSyncService.sync_from_otrs()` | Mock `OtrsZnunyClient.list_queues()` → assert upsert completes |
| Unit | `QueueSyncService.get_topology()` | Seed in-memory DB → assert tree structure matches N1/N2/N3 + children |
| Unit | `QueueSyncService.ensure_seeded()` | Empty in-memory DB → call ensure → assert 11 rows |
| Unit | `QueueStrategyService` backward compat | `QueueStrategyService()` (no args) → topology returns hardcoded (existing tests pass) |
| Unit | `QueueStrategyService` DB-backed | `QueueStrategyService(topology=from_db)` → routing decisions correct |
| Unit | `ActionExecutor._resolve_queue()` | In-memory DB with seed data → resolve by category → assert correct Queue name |
| Unit | `ActionExecutor._resolve_queue()` fallback | DB without matching queue → falls back to `default_queue` setting |
| Integration | API endpoint `/queues/topology` | Test client with seeded DB → assert JSON shape |
| Regression | All existing `test_queue_strategy.py` | Must pass without changes to test code |

## Migration / Rollout

**Migration**: `alembic upgrade head` creates `queues` table and inserts 11 seed rows. No data loss risk — new table only.

**Rollback**:
1. `alembic downgrade -1` — removes `queues` table
2. Revert `QueueStrategyService` to hardcoded `_topology`
3. Revert `ActionExecutor._resolve_queue()` to sync lookup with class-level dicts
4. Delete `QueueSyncService`

## Open Questions

- [ ] ¿OTRS `list_queues()` devuelve `parent_id` o hay que inferir jerarquía por naming convention? (Mitigación: seed topology cubre el caso offline, sync es best-effort)
- [ ] ¿El campo `otrs_external_id` debe mapearse al `external_refs` del domain `Queue` o es un ID directo del OTRS? (Hipótesis: _unwrap_collection incluye un `id` numérico — confirmar con response real)
