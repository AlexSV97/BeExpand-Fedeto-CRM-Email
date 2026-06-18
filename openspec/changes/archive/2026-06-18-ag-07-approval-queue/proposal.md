# Proposal: AG-07 — Cola de aprobaciones pendientes (acciones críticas)

## Intent

Backlog story AG-07 (Épica 6, P0): "Cambios sensibles requieren aprobación
humana". El motor de gobierno (`AgentGovernanceService`) ya produce
recomendaciones por agente (AG-01..06), marca `requires_approval` y soporta
aprobar/rechazar (`POST /agents/approvals`). Pero **no hay forma de ver qué
acciones críticas están pendientes** de decisión: sin esa cola, el human-in-the-
loop es ciego. Esto añade la **cola de aprobaciones pendientes**.

## Scope

### In Scope
- `AgentGovernanceService.list_pending_approvals(db, limit)`: recomendaciones con
  `status="pending"` (requieren aprobación y aún sin decidir), más recientes primero
- `GET /agents/approvals/pending` endpoint
- Tests unitarios + endpoint

### Out of Scope
- Cambiar la política de qué requiere aprobación (ya existe)
- Notificaciones de pendientes (futuro)
- UI

## Capabilities

### New Capabilities
- `agent-approval-queue`: visibilidad de las acciones críticas pendientes de aprobación

### Modified Capabilities
- ninguna (additivo; reusa recommend/approve existentes)

## Approach
1. `list_pending_approvals` consulta `OperationalRecord` con
   `record_kind="agent_recommendation"` y `status="pending"` (al aprobar/rechazar,
   `persist_approval` cambia ese status → salen de la cola). Orden por fecha desc.
2. Endpoint `GET /agents/approvals/pending` devuelve la cola serializada.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/agent_governance.py` | Modified | `list_pending_approvals` |
| `src/api/routers/agents.py` | Modified | `GET /agents/approvals/pending` |
| `tests/test_agent_governance.py` o nuevo | New | Unit + endpoint |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Recomendación queda "pending" tras decidir | Baja | `persist_approval` ya actualiza el status |
| Confundir con history | Baja | Filtra solo kind=agent_recommendation + status=pending |

## Rollback Plan
1. Quitar el endpoint `/agents/approvals/pending`
2. Borrar `list_pending_approvals`
3. Sin cambios de esquema

## Dependencies
- AG-01..06 + aprobar/rechazar (`agent_governance.py`) — hechos.

## Success Criteria
- [ ] `list_pending_approvals` devuelve solo recomendaciones pendientes
- [ ] Tras aprobar/rechazar, la recomendación sale de la cola
- [ ] `GET /agents/approvals/pending` devuelve la cola (auth)
- [ ] Cierra el bucle human-in-the-loop de AG-07
