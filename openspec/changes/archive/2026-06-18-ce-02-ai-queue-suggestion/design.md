# Design: CE-02 — Sugerencia de cola con IA

## Technical Approach

Add a thin AI layer on top of the CE-01 topology. `QueueSuggestionService`
renders the live topology into a compact candidate list, asks the `LLMClient`
to choose the best queue as JSON, validates the choice against the topology, and
returns a unified `QueueSuggestion`. Any failure (no backend, exception, bad
JSON, unknown slug) degrades to `QueueStrategyService.recommend()` mapped into
the same shape with `source="rules"`. The suggestion is exposed on-demand via
`POST /queues/suggestion`; it is never wired into the ingestion hot path.

## Architecture Decisions

### Decision: Reuse rule engine as fallback vs separate heuristic

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Reuse `QueueStrategyService.recommend()` | Single source of routing truth; consistent owners/tiers | **Chosen** |
| New heuristic for fallback | Duplicate logic, drift | Rejected |

### Decision: LLM chooses by slug vs free text

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Constrain output to a `slug` from the candidate list | Easy to validate, low hallucination surface | **Chosen** |
| Free-text queue name | Hard to validate, accent/spacing mismatches | Rejected |

### Decision: Sync vs async topology source

`suggest()` is async (LLM I/O). It accepts a `QueueStrategyService` already built
from the DB (via `QueueStrategyService.create(session)` in the dependency), so
the service itself does no DB I/O.

## Data Flow

```
POST /queues/suggestion
        │
        ▼
QueueStrategyService.create(session) ──► topology() ──► candidates[]
        │                                                   │
        ▼                                                   ▼
QueueSuggestionService.suggest(req) ──► LLMClient.generate(prompt(candidates))
        │                                   │
        │                            parse JSON + validate slug ∈ topology
        │                                   │
        ├── valid ──► QueueSuggestion(source="ai")
        └── invalid/error ──► strategy.recommend(req) ──► QueueSuggestion(source="rules")
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/queue_suggestion.py` | Create | Models + `QueueSuggestionService` + prompt + JSON parsing |
| `src/api/routers/queues.py` | Modify | `POST /queues/suggestion` + dependency |
| `tests/test_queue_suggestion.py` | Create | AI path, fallback, validation, clamp, endpoint |

## Interfaces / Contracts

```python
class QueueSuggestionRequest(BaseModel):
    subject: str
    body_text: str
    category: str | None = None
    urgency: str = "media"
    current_tier: QueueTier = QueueTier.N1

class QueueSuggestionItem(BaseModel):
    queue: Queue
    tier: QueueTier
    owner: str
    confidence: float        # [0,1]
    reason: str

class QueueSuggestion(BaseModel):
    source: Literal["ai", "rules"]
    recommended: QueueSuggestionItem
    alternatives: list[QueueSuggestionItem] = []
    model: str | None = None   # LLM model used (None for rules)

class QueueSuggestionService:
    def __init__(self, strategy: QueueStrategyService, llm_client: LLMClient | None = None)
    async def suggest(self, request: QueueSuggestionRequest) -> QueueSuggestion
```

### Prompt contract

The model receives the candidate list (slug, tier, owner, keywords/name) and the
ticket (subject, body, category, urgency). It MUST answer with strict JSON:

```json
{"slug": "<one of the candidate slugs>", "confidence": 0.0-1.0,
 "reason": "<short>", "alternatives": ["<slug>", "..."]}
```

JSON extraction reuses the tolerant approach from `llm_agent._extract_json`
(strip code fences, locate first `{...}` block).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | AI happy path | Mock `LLMClient.generate` → valid JSON → `source="ai"` |
| Unit | Fallback on exception | `generate` raises → `source="rules"` |
| Unit | Fallback on unknown slug | JSON with bad slug → `source="rules"` |
| Unit | Fallback on bad JSON | prose output → `source="rules"` |
| Unit | Confidence clamp | confidence 1.7 → 1.0 |
| Integration | Endpoint | Test client + auth → 200 + JSON shape (LLM mocked → rules) |

## Migration / Rollout

Additive, no schema change. Rollback = remove route + service file.

## Open Questions

- [ ] ¿Exponer también las colas de negocio (Support/Ventas/…) como candidatas o
  solo la topología N1/N2/N3 + especiales? (Hipótesis: solo topología, igual que
  `recommend()`; las de negocio se enrutan por categoría en `ActionExecutor`.)
