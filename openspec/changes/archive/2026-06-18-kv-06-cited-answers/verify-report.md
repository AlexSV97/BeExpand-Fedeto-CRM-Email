# Verify Report: KV-06 — Citar fuentes en respuestas (RAG con citas)

**Fecha:** 2026-06-18
**Estado:** ✅ Implementado y verificado

## Resumen

Respuesta RAG fundamentada con **citas obligatorias**: `KnowledgeAnswerService`
recupera del vault (`search_rag`), genera una respuesta basada SOLO en esas
fuentes citando `[n]` vía `LLMClient`, y cae a un resumen extractivo determinista
(con citas) si no hay LLM. Nunca inventa fuentes; con vault vacío devuelve
`grounded=False`. Cierra la Épica 5.

## Cambios realizados

| Archivo | Acción | Detalle |
|---------|--------|---------|
| `src/services/knowledge_answer.py` | Nuevo | `KnowledgeAnswerService` + modelos (`KnowledgeAnswer`, `AnswerSource`, `KnowledgeAnswerRequest`) |
| `src/api/routers/knowledge.py` | Modificado | `POST /search/knowledge/answer`; carga de snapshot ahora **best-effort** (robustez, mismo fix que soc.py) |
| `tests/test_knowledge_answer.py` | Nuevo | 6 tests (4 unit + 2 endpoint) |

## Verificación

- **Suite completa**: **380 passed, 5 skipped** (smoke) — antes 374; +6 de KV-06.

## Mapeo de escenarios (spec)

| Escenario | Cobertura |
|-----------|-----------|
| 1 — respuesta IA cita fuentes | `test_ai_answer_cites_sources` |
| 2 — fallback extractivo con `[1]` | `test_extractive_fallback_when_llm_fails` |
| 3 — sin docs → no grounded | `test_no_documents_not_grounded` |
| 4 — fuentes con ref/id/title/excerpt | `test_sources_carry_metadata` |
| 5 — endpoint round-trip | `TestAnswerEndpoint::test_endpoint_returns_answer` |
| 6 — requiere auth | `test_endpoint_requires_auth` |

## Notas de diseño

- RAG estricto: la respuesta se construye SOLO desde los docs recuperados por
  `search_rag`; las `sources` se devuelven siempre (sin alucinar fuentes, NFR-3).
- IA vía `LLMClient` con fallback extractivo determinista (`source="extractive"`);
  `answer()` nunca lanza (NFR-2). En prod sin LLM → extractivo con citas.
- Endurecido `get_knowledge_vault` de `knowledge.py` a carga best-effort (el vault
  funciona en memoria si el store de snapshot falla), igual que en `soc.py`.

## Estado de la Épica 5 — Knowledge Vault / RAG
KV-01 (ingesta cerrados) ✅ · KV-02 (notas/runbooks seed) ✅ · KV-03 (embeddings) ✅ ·
KV-04 (búsqueda semántica) ✅ · KV-05 (reranking) ✅ · KV-06 (citas en respuestas) ✅
→ **épica funcionalmente completa**.

## Pendiente menor (Open Question)
Hay dos instancias de vault en `app.state` (`soc.py`→`knowledge_vault_service`,
`knowledge.py`→`knowledge_vault`). Unificarlas es una mejora futura.
