# Verify Report: CE-03 — Escalado N-niveles

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Escalado N-niveles consciente de la jerarquía sobre la topología persistida
(CE-01). `EscalationService` calcula un `EscalationPlan` recorriendo la cadena de
tiers (N1→N2→N3) hacia un tier objetivo explícito o, por defecto, al siguiente
nivel, con camino multi-nivel (`steps`). Lógica pura, nunca lanza. El endpoint
SOC de escalado se reconecta al servicio (tier actual desde la cola real del
ticket, honra `target_tier`), conservando su shape.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/escalation.py` | Nuevo | `EscalationService` + modelos (`EscalationRequest/Step/Plan`) |
| `src/api/routers/queues.py` | Modificado | `POST /queues/escalate` |
| `src/api/routers/soc.py` | Modificado | endpoint escalate usa `EscalationService` (tier actual desde el ticket, honra target) |
| `tests/test_escalation.py` | Nuevo | 11 tests (9 unit + 2 endpoint) |

## Verificación

- **CE-03 + SOC**: `pytest tests/test_escalation.py tests/api/test_soc_router.py` → **61 passed**.
- **Suite completa**: **301 passed, 0 failed** (antes 290; +11 de CE-03).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — auto sube un nivel | `test_auto_escalation_goes_one_level_up` |
| 2 — target explícito + path | `test_explicit_target_with_multilevel_path` |
| 3 — target no superior = no-op | `test_target_not_higher_is_noop` / `test_target_equal_is_noop` |
| 4 — ya en el tope | `test_top_tier_is_noop` |
| 5 — tier desde slug | `test_resolves_current_tier_from_slug` |
| 6 — endpoint serializa plan | `TestEscalateEndpoint::test_endpoint_returns_plan` |
| 7 — SOC escalate conserva contrato | `TestPostEscalateTicket` (toda la clase pasa) |

## Notas de diseño

- La cadena de escalado es por **rango de tier** (n1<n2<n3), no por `parent_id`:
  en el seed de CE-01 los tiers N son raíces y `parent_id` solo enlaza especiales
  con su tier. Coherente con `_tier_rank` ya existente en `QueueStrategyService`.
- No-op total: target ≤ actual o ya en el tope → `should_escalate=False`,
  `to_tier=from_tier`, `steps=[]`. `escalate()` nunca lanza (REQ-1).
- El registro/persistencia de escalados queda para **CE-04** (escalation recording).
- Open Question resuelta: las colas especiales son terminales en auto-escalado
  (sin siguiente nivel en la cadena N).
