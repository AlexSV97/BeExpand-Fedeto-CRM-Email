# Proposal: RP-04 — Dashboard de observabilidad

## Intent

Backlog story RP-04 (Épica 7): "Hay vista de logs, latencia, coste y fallos".
El resto de la Épica 7 está (KPIs RP-01, daily/weekly RP-02/03, feedback RP-05,
sugerencias RP-06), pero no hay una **vista de observabilidad** del sistema. Esto
añade un endpoint de observabilidad que agrega, a partir de datos reales: estado
de integraciones, modo operativo, recuentos de actividad y fallos
(`OperationalRecord`) e intervalos de los jobs de fondo.

## Scope

### In Scope
- `ObservabilityService`: snapshot agregado (integraciones, modo, recuentos por
  `record_kind`, fallos, intervalos de auto-sync/SLA)
- `GET /reporting/observability` endpoint
- Tests unitarios + endpoint

### Out of Scope
- Instrumentación real de **latencia/coste** por petición/LLM (requiere
  middleware de métricas; se documenta como siguiente paso)
- Exportar a Prometheus/OTel
- UI

## Capabilities

### New Capabilities
- `observability-snapshot`: vista de salud + actividad + fallos del sistema

### Modified Capabilities
- ninguna (additivo)

## Approach
1. `ObservabilityService(db, settings, otrs_configured)` agrega:
   - integraciones: database (DB alcanzable), OTRS (configurado), AI (OpenRouter
     vs Ollama local)
   - operatingMode derivado (OTRS configurado → live-capable, si no demo)
   - recordCounts por `record_kind` (group by) y `failures` (estados de fallo)
   - intervals: `sync_interval_seconds`, `sla_alert_scan_interval_seconds`
2. `GET /reporting/observability` devuelve el snapshot.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/observability.py` | New | `ObservabilityService` + modelos |
| `src/api/routers/reporting.py` | Modified | `GET /reporting/observability` |
| `tests/test_observability.py` | New | Unit + endpoint |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Probes en vivo añaden latencia/flaky | Media | Estado basado en config + DB; sin llamadas de red externas |
| "latencia/coste" no disponibles | Esperado | Documentado; el MVP cubre salud + actividad + fallos |

## Rollback Plan
1. Quitar el endpoint `/reporting/observability`
2. Borrar `ObservabilityService`
3. Sin cambios de esquema

## Dependencies
- `OperationalRecord` (datos), `OtrsZnunySettings`, `Settings` — disponibles.

## Success Criteria
- [ ] El snapshot incluye estado de integraciones, modo, recuentos y fallos
- [ ] No hace llamadas de red externas (rápido y determinista)
- [ ] `GET /reporting/observability` devuelve el snapshot (auth)
