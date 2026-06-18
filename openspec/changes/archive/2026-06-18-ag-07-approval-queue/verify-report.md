# Verify Report: AG-07 — Cola de aprobaciones pendientes

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Cola de aprobaciones pendientes para acciones críticas (human-in-the-loop):
`AgentGovernanceService.list_pending_approvals` devuelve las recomendaciones con
`status="pending"` (requieren aprobación y sin decidir); al aprobar/rechazar salen
de la cola. Endpoint `GET /agents/approvals/pending`. Cierra el bucle de AG-07
(antes se podía recomendar y aprobar por id, pero no **ver** lo pendiente).

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/agent_governance.py` | Modificado | `list_pending_approvals(db, limit)` (kind=agent_recommendation, status=pending, desc) |
| `src/api/routers/agents.py` | Modificado | `GET /agents/approvals/pending` (reusa `OperationalHistoryResponse`) |
| `tests/test_agent_approval_queue.py` | Nuevo | 5 tests (3 unit + 2 endpoint) |

## Verificación

- **Suite completa**: **385 passed, 5 skipped** (smoke) — antes 380; +5 de AG-07.

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — recomendación que requiere aprobación aparece pendiente | `test_recommendation_requiring_approval_is_pending` |
| 2 — auto-aprobada no aparece | `test_auto_approved_not_pending` |
| 3 — aprobar la saca de la cola | `test_approving_removes_from_queue` |
| 4 — endpoint devuelve la cola | `TestPendingApprovalsEndpoint::test_endpoint_lists_pending` |
| 5 — requiere auth | `test_endpoint_requires_auth` |

## Notas de diseño

- Reutiliza los `OperationalRecord` que ya escribe el gobierno
  (`record_kind="agent_recommendation"`); `persist_approval` ya cambia el status
  al decidir, así que la cola se vacía sola. Sin tabla nueva.
- Serialización y orden consistentes con `/agents/history`.

## Estado de la Épica 6 — Agentes + gobierno
AG-01 Triage · AG-02 SLA · AG-03 Knowledge · AG-04 Response · AG-05 Escalation ·
AG-06 Compliance (todos en `AgentGovernanceService.recommend`, con
`requires_approval` por agente) ✅ · AG-07 aprobación de acciones críticas
(recommend → cola pendientes → approve/reject) ✅ → **épica funcionalmente completa**.
