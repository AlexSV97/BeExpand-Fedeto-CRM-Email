# Verify Report: CE-04 — Registro de escalados

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Historial de escalados persistido y consultable. Cada escalado (CE-03) se guarda
como `OperationalRecord` con `record_kind="escalation"` (sin tabla/migración
nueva), almacenando el `EscalationPlan` completo. El endpoint SOC de escalado
registra cada escalado (best-effort) y un nuevo endpoint expone el histórico por
ticket.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/escalation_recording.py` | Nuevo | `EscalationRecordService` (`record`, `list_for_ticket`, `list_all`, `to_item`) + modelos `EscalationHistoryItem/Response` |
| `src/api/routers/soc.py` | Modificado | grabación best-effort en `escalate`; `GET /soc/tickets/{id}/escalations` |
| `tests/test_escalation_recording.py` | Nuevo | 9 tests (6 unit + 3 endpoint) |

## Verificación

- **CE-04 + SOC**: `pytest tests/test_escalation_recording.py tests/api/test_soc_router.py` → todo verde.
- **Suite completa**: **310 passed, 0 failed** (antes 301; +9 de CE-04).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — graba fila de escalado | `TestRecord::test_record_persists_escalation_row` |
| 2 — no-op con status "noop" | `test_noop_plan_recorded_with_noop_status` |
| 3 — histórico newest-first | `test_history_newest_first` (timestamps explícitos) |
| 4 — histórico por ticket | `test_history_is_ticket_scoped` |
| 5 — escalate crea registro | `TestEscalationHistoryEndpoint::test_escalate_then_history_returns_record` |
| 6 — endpoint requiere auth | `test_history_requires_auth` |
| 7 — fallo de grabación no rompe escalate | `test_recording_failure_does_not_break_escalate` |

## Notas de diseño

- Reutiliza `OperationalRecord` (`record_kind="escalation"`), igual que
  agent_recommendation/agent_approval/audit_event — sin migración (NFR-1).
- Grabación best-effort en el endpoint (try/except), nunca rompe el escalado
  (NFR-2), como ya hace la propagación a OTRS.
- Aislamiento: las queries existentes (`list_history`, `query_audit_events`)
  filtran kinds explícitos, así que los registros `"escalation"` no las
  contaminan (REQ-6).
- Ordenación newest-first por `created_at desc`; en SQLite `CURRENT_TIMESTAMP` es
  de resolución de segundo, por lo que el test de orden usa timestamps explícitos.
- `list_all()` incluido para un futuro histórico global; el endpoint inicial es
  per-ticket (Open Question).

## Estado de la serie CE
CE-01 ✅ · CE-02 ✅ · CE-03 ✅ · CE-04 ✅ — serie de colas/escalado completa.
