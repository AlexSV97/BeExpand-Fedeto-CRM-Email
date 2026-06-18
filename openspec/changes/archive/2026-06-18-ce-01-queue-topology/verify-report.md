# Verify Report: CE-01 — Modelar árbol de colas

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Topología de colas unificada en una tabla `queues` con FK auto-referencial,
sincronizable desde OTRS con seed de fallback. Reemplaza las dos topologías
hardcoded inconsistentes (`QueueStrategyService._topology` y
`ActionExecutor.QUEUE_MAP`/`DEPARTMENT_QUEUE_MAP`).

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/db/models.py` | Modificado | `QueueModel` con FK self-ref (`parent_id`); atributo `queue_metadata` → columna SQL `metadata` |
| `src/domain/ticketing.py` | Modificado | `Queue` gana `parent_id`, `tier`, `owner` (REQ-6) |
| `src/services/queue_sync.py` | Nuevo | `QueueSyncService`: `sync_from_otrs`, `ensure_seeded`, `get_topology`, `get_by_name` |
| `src/services/queue_strategy.py` | Modificado | `__init__(topology=None)` + factory async `create(session)` + dependencia DB-backed (fail-open) |
| `src/agents/action_executor.py` | Modificado | `_validate_queue()` async valida contra BD; fallback a `default_queue` (REQ-4); invocado en `_create_ticket` |
| `alembic/versions/b1d4c0a7e2f1_*.py` | Nuevo | Crea `queues` + seed de 11 filas (down_revision `2a8e3f5b9c10`) |
| `tests/test_queue_sync.py` | Nuevo | 16 tests: seed, topología, sync, fallback, strategy DB-backed, validación ActionExecutor |

## Verificación

- **Suite CE-01 + regresión cercana**: `pytest tests/test_queue_sync.py tests/test_queue_strategy.py tests/test_action_executor.py` → **57 passed**.
- **Suite completa**: 268 passed, 5 failed. Los 5 fallos (`test_soc_router.py`: priority filter / knowledge vault) son **preexistentes en `main`** (confirmado con `git stash`), no relacionados con CE-01.
- **Migración**: render offline `alembic upgrade 2a8e3f5b9c10:b1d4c0a7e2f1 --sql` válido — `CREATE TABLE queues` con FK self-ref + UNIQUE(name)/UNIQUE(slug) + 11 INSERT con `parent_id` correcto (4,5→3; 6→2).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — topología carga desde BD con parent-child | `TestGetTopology` |
| 2 — sync OTRS crea/actualiza | `TestSyncFromOtrs::test_sync_upserts_otrs_queues`, `test_sync_infers_parent_for_known_specials` |
| 3 — OTRS caído → seed (6 filas) | `test_sync_falls_back_to_seed_when_otrs_unreachable` |
| 4 — ActionExecutor valida contra BD | `TestActionExecutorValidateQueue::test_validates_existing_queue` |
| 5 — recommend basado en topología BD | `TestQueueStrategyDbBacked::test_recommend_routes_incident_to_n2_from_db_topology` |
| 6 — cola desconocida → default | `test_unknown_queue_falls_back_to_default` |

## Notas de diseño

- `QUEUE_MAP`/`DEPARTMENT_QUEUE_MAP` se conservan como política de routing
  categoría→cola (NFR-1 lo permite); la BD valida la existencia. `_resolve_queue`
  se mantiene síncrono (compatibilidad), la validación contra BD se añade como
  capa async en `_create_ticket` (fail-open: nunca bloquea la creación de ticket).
- `ensure_seeded()` siembra 6 nodos de topología (Scenario 3); la migración
  Alembic siembra 11 (incluye colas de negocio Support/Ventas/… necesarias para
  la validación de `_validate_queue`).
- Atributo ORM `queue_metadata` mapeado a columna `metadata` (el nombre
  `metadata` está reservado por la Base declarativa de SQLAlchemy).
