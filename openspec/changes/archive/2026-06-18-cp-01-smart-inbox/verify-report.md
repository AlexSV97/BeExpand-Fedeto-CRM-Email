# Verify Report: CP-01 — Bandeja inteligente

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

La bandeja (`GET /soc/tickets`) ahora es un smart inbox: cada fila lleva riesgo
SLA (SLA-04), cola sugerida (CE-02 vía reglas), owner y cola actual, además de
prioridad/estado. Enriquecimiento en memoria, resiliente por fila.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/api/routers/soc.py` | Modificado | `TicketItem` + campos `owner/queue/slaRisk/slaRemainingMinutes/suggestedQueue`; helper `_enrich_ticket_item`; la lista lo usa |
| `tests/test_smart_inbox.py` | Nuevo | 6 tests (4 unit + 2 endpoint) |

## Verificación

- **Suite completa**: **348 passed, 0 failed** (antes 342; +6 de CP-01).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — filas con riesgo SLA + cola sugerida | `TestSmartInboxEndpoint::test_rows_are_enriched` |
| 2 — cola sugerida es slug real | `test_computes_risk_and_suggested_queue` / `test_incident_suggests_n2` |
| 3 — owner presente | `test_computes_risk_and_suggested_queue` |
| 4 — comportamiento previo preservado | `test_filtering_preserved` + `TestGetTicketQueue` |
| 5 — enriquecimiento resiliente | `test_resilient_to_assess_failure` |

## Notas de diseño

- Cola sugerida vía `QueueStrategyService.recommend` (**reglas**, no LLM) para
  latencia microsegundos por fila; la sugerencia IA (CE-02) sigue en su endpoint.
- Riesgo SLA vía `TicketLifecycleService.assess` (solo si el ticket tiene SLA).
- Enriquecimiento por fila envuelto en try/except: un ticket problemático deja sus
  campos enriquecidos en null sin romper la lista (REQ-5).
- Campos nuevos opcionales → sin romper consumidores existentes (additive).

## Estado de la Épica 4 — Smart Queue + Copilot
- **CP-01 Bandeja inteligente** ✅ (este cambio)
- CP-02 Vista detalle / CP-03 Resumen / CP-04 Casos similares — cubiertos por
  `GET /soc/tickets/{id}/copilot` (contexto + resumen vía agentes + RAG similar cases)
- CP-07 Aprobación humana — `AgentGovernanceService.approve` + endpoints existentes
- Pendiente real: **CP-05/CP-06** (borradores de primera respuesta / nota interna)
  — existe `ReplySuggesterAgent` pero sin endpoint dedicado de copilot drafts.
