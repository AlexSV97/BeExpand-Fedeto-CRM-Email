# Verify Report: CP-05 / CP-06 — Borradores de respuesta y nota interna

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

`TicketDraftService` genera borradores asistidos por IA para un ticket: respuesta
al cliente (CP-05) y nota interna (CP-06), con fallback determinista a plantilla
cuando no hay LLM. Cada borrador lleva `requires_approval=True` y nunca se envía
(CP-07). Endpoint `POST /soc/tickets/{id}/draft`.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/ticket_drafts.py` | Nuevo | `TicketDraftService` + `DraftResult` (AI + plantilla) |
| `src/api/routers/soc.py` | Modificado | `POST /soc/tickets/{id}/draft?kind=customer_reply\|internal_note` |
| `tests/test_ticket_drafts.py` | Nuevo | 7 tests (4 unit + 3 endpoint) |

## Verificación

- **Suite completa**: **355 passed, 0 failed** (antes 348; +7 de CP-05/06).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — respuesta cliente IA | `test_ai_customer_reply` |
| 2 — nota interna | `test_internal_note_kind` |
| 3 — fallback ante error LLM | `test_fallback_when_llm_raises` |
| 4 — fallback ante salida vacía | `test_fallback_when_llm_empty` |
| 5 — endpoint round-trip | `TestDraftEndpoint::test_endpoint_returns_draft` |
| 6 — kind inválido → 422 | `test_invalid_kind_rejected` |
| 7 — requiere auth | `test_requires_auth` |

## Notas de diseño

- IA vía `LLMClient` con fallback determinista a plantilla (`source="template"`);
  `draft()` nunca lanza (NFR-2). En prod sin LLM accesible → plantilla.
- `requires_approval=True` en todo borrador; el servicio **solo redacta**, nunca
  envía (CP-07, human-in-the-loop).
- Servicio orientado a `Ticket` (no reusa `ReplySuggesterAgent`, que es del
  pipeline de email) para soportar reply + nota interna desde el ticket.

## Estado de la Épica 4 — Smart Queue + Copilot
- CP-01 Bandeja inteligente ✅
- CP-02 Vista detalle / CP-03 Resumen / CP-04 Casos similares — `GET /soc/tickets/{id}/copilot` ✅
- CP-05 Borrador primera respuesta ✅ · CP-06 Borrador nota interna ✅ (este cambio)
- CP-07 Aprobación humana — `AgentGovernanceService.approve` + `requires_approval` en borradores ✅
→ **Épica 4 funcionalmente completa.**
