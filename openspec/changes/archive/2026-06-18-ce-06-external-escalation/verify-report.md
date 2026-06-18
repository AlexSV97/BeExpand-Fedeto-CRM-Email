# Verify Report: CE-06 — Escalado a fabricante / ITSM externo

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Handoff de un ticket a un destino externo (fabricante / ITSM externo): enruta a la
cola especial de CE-01, genera una referencia de tracking (`ExternalRef`) y
persiste el handoff como `OperationalRecord` (`record_kind="external_escalation"`).
Propagación best-effort a OTRS (mover a la cola especial). **Cierra la Épica 2.**

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/external_escalation.py` | Nuevo | `ExternalEscalationService` + modelos + mapa destino→cola especial |
| `src/api/routers/soc.py` | Modificado | `POST .../escalate-external`, `GET .../external-escalations` |
| `tests/test_external_escalation.py` | Nuevo | 8 tests (5 unit + 3 endpoint) |

## Verificación

- **Suite completa**: **328 passed, 0 failed** (antes 320; +8 de CE-06).

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — fabricante → special-fabricante | `test_manufacturer_resolves_special_queue` |
| 2 — external_id provisto | `test_uses_provided_external_id` |
| 3 — external_id generado | `test_generates_external_id_when_missing` |
| 4 — persistido y listable | `test_persists_and_lists` |
| 5 — destino desconocido → 422 | `test_unknown_destination_rejected` |
| 6 — endpoint round-trip | `test_escalate_external_then_history` |
| 7 — requiere auth | `test_requires_auth` |

## Notas de diseño

- La **entrega real** a la API del fabricante/ITSM queda fuera de alcance; el
  artefacto duradero y consultable es la `ExternalRef` de tracking (system=destino,
  entity_type="external_case", external_id provisto o generado `PREFIX-XXXXXXXX`).
- Reutiliza las **colas especiales** de CE-01 (`special-fabricante`,
  `special-external-itsm`) y valida el slug contra la topología viva.
- Destino inválido → `ValueError` en el servicio / **422** en el endpoint (validador
  pydantic); fallo de OTRS nunca rompe el flujo (best-effort).
- `created_at` explícito (microseg) para orden determinista, como en CE-05.
- Aislamiento: los registros `"external_escalation"` no contaminan las queries
  existentes (audit/recommendation/escalation/ownership).

## Estado de la Épica 2 — Colas y escalado
CE-01 ✅ · CE-02 ✅ · CE-03 ✅ · CE-04 ✅ · CE-05 ✅ · CE-06 ✅ — **épica completa**.
