# Proposal: KV-06 — Citar fuentes en respuestas (RAG con citas)

## Intent

Backlog story KV-06 (Épica 5) y principio transversal del proyecto: "Toda
respuesta IA referencia el origen del conocimiento". Hoy el Knowledge Vault
recupera documentos (KV-04/05) pero no existe una **respuesta generada y
fundamentada** que **cite sus fuentes**. Esto añade un servicio/endpoint de
respuesta RAG: recupera del vault, genera una respuesta basada SOLO en esas
fuentes y devuelve la respuesta junto con las citas (id/título/extracto).

## Scope

### In Scope
- `KnowledgeAnswerService`: recupera (search_rag), genera respuesta fundamentada
  vía `LLMClient` citando `[n]`, con **fallback extractivo determinista**
- Devuelve siempre las `sources` (citas) usadas
- `POST /search/knowledge/answer` endpoint (auth)
- Tests unitarios + endpoint

### Out of Scope
- Reentrenar/afinar modelos; nuevos backends LLM (reusa `LLMClient`)
- Ingesta dinámica de runbooks (KV-02 ya cubierto por seed)
- Cambiar el ranking (reusa `search_rag`)

## Capabilities

### New Capabilities
- `knowledge-cited-answers`: respuesta RAG fundamentada con citas obligatorias

### Modified Capabilities
- ninguna (additivo sobre el vault existente)

## Approach
1. `KnowledgeAnswerService(vault, llm_client=None).answer(query, limit)`.
2. `search_rag` → top-k docs; si no hay → respuesta "sin información" sin fuentes.
3. Prompt fundamentado con fuentes numeradas; el LLM responde citando `[n]` y
   SOLO con esas fuentes.
4. Fallback extractivo (concatena extractos de las top fuentes con `[n]`) si el
   LLM no está disponible/vacío. Nunca lanza.
5. Devuelve `{query, answer, sources[], source: ai|extractive, grounded}`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/knowledge_answer.py` | New | `KnowledgeAnswerService` + modelos |
| `src/api/routers/knowledge.py` | Modified | `POST /search/knowledge/answer` (+ snapshot load best-effort) |
| `tests/test_knowledge_answer.py` | New | Unit + endpoint |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM no disponible en prod | Alta | Fallback extractivo con citas (`source="extractive"`) |
| Respuesta sin fuentes (alucinación) | Media | Se construye SOLO desde docs recuperados; sources siempre presentes |
| Vault vacío | Media | `grounded=False` + mensaje claro, sin inventar |

## Rollback Plan
1. Quitar el endpoint `POST /search/knowledge/answer`
2. Borrar `KnowledgeAnswerService`
3. Sin cambios de esquema

## Dependencies
- KV-04/05 (`search_rag`) — hechos. `LLMClient` — disponible.

## Success Criteria
- [ ] La respuesta cita las fuentes recuperadas (`sources` no vacío cuando hay docs)
- [ ] Cae a extractivo con citas si el LLM no está disponible
- [ ] Vault vacío → `grounded=False` sin inventar fuentes
- [ ] Endpoint `POST /search/knowledge/answer` devuelve la respuesta + auth
