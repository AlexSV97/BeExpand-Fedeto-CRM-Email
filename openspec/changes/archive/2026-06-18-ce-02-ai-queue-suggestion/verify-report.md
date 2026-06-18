# Verify Report: CE-02 — Sugerencia de cola con IA

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Capa de IA sobre la topología de colas (CE-01): `QueueSuggestionService` pide al
`LLMClient` la mejor cola de entre las candidatas de la topología viva (con
confianza, motivo y alternativas) y degrada de forma determinista a
`QueueStrategyService.recommend()` (`source="rules"`) ante cualquier fallo.
On-demand vía `POST /queues/suggestion`; no toca el hot-path de ingestión.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/queue_suggestion.py` | Nuevo | Modelos (`QueueSuggestionRequest/Item/Suggestion`) + `QueueSuggestionService` + prompt + parsing JSON tolerante + clamp de confianza |
| `src/api/routers/queues.py` | Modificado | `POST /queues/suggestion` (auth, reusa `get_queue_strategy_service`) |
| `tests/test_queue_suggestion.py` | Nuevo | 13 tests |

## Verificación

- **CE-02**: `pytest tests/test_queue_suggestion.py` → **13 passed**.
- **Suite completa**: **285 passed, 5 failed**. Los 5 fallos (`test_soc_router.py`)
  son **preexistentes en `main`** (confirmado con `git stash` en CE-01), no
  relacionados con CE-02.

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — IA sugiere cola válida | `TestSuggestAi::test_ai_suggests_valid_queue` |
| 2 — LLM caído → reglas | `TestFallback::test_falls_back_when_llm_raises` |
| 3 — cola desconocida → reglas | `test_falls_back_on_unknown_slug` |
| 4 — JSON malformado → reglas | `test_falls_back_on_malformed_json` |
| 5 — endpoint serializa sugerencia | `TestSuggestionEndpoint::test_endpoint_returns_suggestion` |
| 6 — confianza clamped | `test_ai_confidence_is_clamped` |

## Notas de diseño

- El slug elegido por el LLM se valida contra la topología (REQ-3); alternativas
  desconocidas o duplicadas se filtran.
- `suggest()` nunca lanza (NFR-3): cualquier excepción/JSON inválido/cola
  desconocida cae a reglas.
- En tests y en prod sin backend LLM accesible, el endpoint responde
  `source="rules"` de forma determinista (NFR-2: política free-tier + reglas).
- Solo se ofrecen como candidatas las colas de topología (N1/N2/N3 + especiales),
  igual que `recommend()`; las colas de negocio se enrutan por categoría en
  `ActionExecutor` (Open Question resuelta en este sentido).
