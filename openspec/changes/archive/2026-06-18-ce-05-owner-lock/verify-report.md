# Verify Report: CE-05 — Gestión de owner/lock por ticket

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Owner y lock por ticket ahora rastreables: asignar propietario, lock/unlock,
consultar estado actual e historial. Cada cambio se persiste como
`OperationalRecord` con `record_kind="ownership"` guardando un snapshot completo
del estado resultante. Propagación best-effort del owner a OTRS. Sin tabla nueva.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/ticket_ownership.py` | Nuevo | `TicketOwnershipService` + modelos (`OwnershipState/HistoryItem/Response`) |
| `src/api/routers/soc.py` | Modificado | `POST .../assign`, `.../lock`, `.../unlock`, `GET .../ownership` |
| `src/config.py` | Modificado | `Settings.Config.extra="ignore"` (no fallar por env vars ajenas como `RENDER_API_KEY`) |
| `tests/test_ticket_ownership.py` | Nuevo | 10 tests (6 unit + 4 endpoint) |

## Verificación

- **Suite completa**: **320 passed, 0 failed** (antes 310; +10 de CE-05).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — assign fija owner | `test_assign_sets_owner` |
| 2 — lock fija locked+locked_by | `test_lock_sets_locked_and_locked_by` |
| 3 — unlock limpia lock, mantiene owner | `test_unlock_clears_lock_keeps_owner` |
| 4 — estado actual = último cambio | `test_current_state_is_latest_change` |
| 5 — default vacío ticket desconocido | `test_empty_default_for_unknown_ticket` |
| 6 — endpoint assign round-trip | `TestOwnershipEndpoints::test_assign_then_get_ownership` |
| 7 — endpoints requieren auth | `test_ownership_requires_auth` |

## Notas de diseño / incidencias

- **Fix colateral importante**: añadir `RENDER_API_KEY` al `.env` rompía el arranque
  (el `Settings` de pydantic prohibía extras). Se cambió a `extra="ignore"` para
  ignorar variables de entorno operativas ajenas a la app. Sin esto, la app
  fallaría al iniciar en cualquier entorno con esa key.
- **Orden determinista**: el snapshot del estado se ordena por `created_at desc`;
  como el `server_default` de SQLite es de resolución de segundo y el PK es UUID
  (no monótono), un flujo assign→lock→unlock empataba timestamps y `current_state`
  podía devolver el registro equivocado. Se fija `created_at` explícito con
  precisión de microsegundo en el servicio.
- Lock **advisory** (registrado/consultable), sin enforcement de concurrencia
  (fuera de alcance). Aislamiento: los registros `"ownership"` no aparecen en las
  queries existentes de audit/recommendation/escalation.
