# Verify Report: SLA-05 — Generar alertas tempranas

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Alertas tempranas de SLA: `SlaAlertService` escanea tickets, detecta los que están
en riesgo (watch/high/critical) **antes** del vencimiento usando
`TicketLifecycleService` (SLA-01..04), genera alertas idempotentes (sin duplicar
en scans repetidos), las persiste como `OperationalRecord`
(`record_kind="sla_alert"`) y notifica best-effort (Telegram) en high/critical.
Cierra el hueco de la Épica 3.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/sla_alerts.py` | Nuevo | `SlaAlertService` + modelos (`SlaAlert`, `SlaAlertScanResponse`, `SlaAlertListResponse`) |
| `src/api/routers/soc.py` | Modificado | `POST /soc/sla/alerts/scan`, `GET /soc/sla/alerts`, `POST /soc/sla/alerts/{id}/ack` |
| `tests/test_sla_alerts.py` | Nuevo | 11 tests (7 unit + 4 endpoint) |

## Verificación

- **Suite completa**: **339 passed, 0 failed** (antes 328; +11 de SLA-05).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — ticket en riesgo genera alerta | `test_at_risk_ticket_raises_alert` |
| 2 — ticket sano sin alerta | `test_healthy_ticket_no_alert` |
| 3 — re-scan no duplica | `test_rescan_does_not_duplicate` |
| 4 — escalada de riesgo crea alerta | `test_risk_escalation_creates_new_alert` |
| 5 — ticket sin SLA omitido | `test_ticket_without_sla_skipped` |
| 6 — ack quita de activas | `test_acknowledge_removes_from_active` |
| 7 — endpoints + auth | `TestSlaAlertEndpoints` |

## Notas de diseño

- **Dedup idempotente** por ticket + rango de riesgo: no crea alerta si ya existe
  una sin reconocer de riesgo igual o superior; una escalada (watch→high) sí crea
  una nueva (NFR-2).
- **Notificación best-effort** reutilizando `TelegramNotifier` (gated por
  `enabled`); fallo nunca rompe el scan (NFR-3). Riesgo→urgencia: high/critical→alta.
- Scan **on-demand** vía endpoint; cablear un cron / `_auto_sync_loop` queda como
  follow-up (Open Question).
- `created_at` explícito microseg para orden determinista; aislamiento de
  `"sla_alert"` respecto a otras queries por record_kind.

## Estado de la Épica 3 — Ciclo de vida + SLA
SLA-01..04 (`TicketLifecycleService`) ✅ · SLA-05 (alertas tempranas) ✅ ·
SLA-06 (War Room `GET /soc/sla`) ✅ — **épica funcionalmente completa**.
