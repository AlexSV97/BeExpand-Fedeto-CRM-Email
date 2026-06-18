# Design: KV-06 — Citar fuentes en respuestas

## Technical Approach

`KnowledgeAnswerService` wraps the existing `KnowledgeVaultService`. It retrieves
top-k documents with `search_rag`, builds a grounded prompt with numbered sources,
and asks the `LLMClient` to answer using only those sources and cite `[n]`. Any
failure (no LLM, empty output) degrades to a deterministic extractive answer built
from the source excerpts with `[n]` citations. The answer always returns the
`sources` used; with no retrieval it returns `grounded=False` and no sources.
Exposed via `POST /search/knowledge/answer`. Mirrors CE-02/CP-05 AI-with-fallback.

## Architecture Decisions

### Decision: Ground strictly on retrieved docs

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Build answer only from `search_rag` hits + always return sources | No hallucinated sources; verifiable | **Chosen** |
| Free-form LLM answer | Fast but unverifiable, violates "citas obligatorias" | Rejected |

### Decision: Extractive fallback over failure

Prod often has no reachable LLM; an extractive answer (top excerpts + citations)
keeps the feature useful and still cited, on-policy with the rest of the app.

## Data Flow

```
POST /search/knowledge/answer {query, limit}
   results = vault.search_rag(query, limit)
   if not results.items: → KnowledgeAnswer(grounded=False, sources=[])
   sources = numbered(results.items)
   LLM.generate(prompt(query, sources))  → cites [n]   (source="ai")
       error/empty → extractive(top excerpts + [n])     (source="extractive")
   → KnowledgeAnswer(answer, sources, source, grounded=True)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/knowledge_answer.py` | Create | `KnowledgeAnswerService` + models |
| `src/api/routers/knowledge.py` | Modify | `POST /search/knowledge/answer`; snapshot load made best-effort |
| `tests/test_knowledge_answer.py` | Create | Unit + endpoint |

## Interfaces / Contracts

```python
class AnswerSource(BaseModel):
    ref: int            # 1-based citation index
    id: str
    title: str
    excerpt: str
    score: float = 0.0

class KnowledgeAnswerRequest(BaseModel):
    query: str
    limit: int = 4

class KnowledgeAnswer(BaseModel):
    query: str
    answer: str
    sources: list[AnswerSource]
    source: Literal["ai", "extractive", "none"]
    grounded: bool

class KnowledgeAnswerService:
    def __init__(self, vault: KnowledgeVaultService, llm_client: LLMClient | None = None)
    async def answer(self, query: str, limit: int = 4) -> KnowledgeAnswer
```

Prompt: numbered sources (`[1] <title>: <excerpt>`), instruction to answer in
Spanish using only the sources and cite `[n]`, and to say it lacks info if the
sources don't cover it.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | AI answer cites (Sc.1) | vault w/ docs + FakeLLM → source ai, sources non-empty |
| Unit | extractive fallback (Sc.2) | RaisingLLM → source extractive, `[1]` in text |
| Unit | no docs (Sc.3) | empty vault → grounded False, sources [] |
| Unit | source fields (Sc.4) | assert ref/id/title/excerpt |
| Integration | endpoint (Sc.5) | client → 200 + shape |
| Integration | auth (Sc.6) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoint + service.

## Open Questions

- [ ] ¿Unificar las dos instancias de vault (soc.py usa `knowledge_vault_service`,
  knowledge.py usa `knowledge_vault`)? Fuera de alcance; se documenta.
