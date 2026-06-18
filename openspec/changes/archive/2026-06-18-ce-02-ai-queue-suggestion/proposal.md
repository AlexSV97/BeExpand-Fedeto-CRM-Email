# Proposal: CE-02 — Sugerencia de cola con IA

## Intent

The DB-backed queue topology (CE-01) is routed today only by hardcoded keyword
rules in `QueueStrategyService.recommend()`. This adds an AI layer that suggests
the best queue from the live topology — with confidence, reasoning and ranked
alternatives — while keeping the rule-based path as a deterministic fallback
(on-policy: free LLM tier + rule-based fallback).

## Scope

### In Scope
- `QueueSuggestionService`: LLM picks a queue from the DB topology candidates
- Deterministic fallback to `QueueStrategyService.recommend()` when the LLM is
  unavailable, errors, or returns an invalid/unknown queue
- Suggestion validated against the topology (slug must exist)
- `POST /queues/suggestion` endpoint
- Unit tests (AI happy path mocked, fallback paths, validation)

### Out of Scope
- Auto-applying the suggestion to a ticket (human-in-the-loop stays manual)
- N-level escalation (CE-03), escalation recording (CE-04)
- Training/fine-tuning, embeddings-based routing
- Changing `ActionExecutor` ticket creation flow

## Capabilities

### New Capabilities
- `queue-suggestion-ai`: AI-assisted queue recommendation over the persisted topology

### Modified Capabilities
- none (additive; `queue-routing-strategy` is reused as fallback)

## Approach
1. `QueueSuggestionService(strategy, llm_client=None)` builds the candidate list
   from `strategy.topology()` (roots + specials).
2. Prompt the LLM to return JSON: chosen `slug`, `confidence`, `reason`, ranked
   `alternatives`.
3. Parse + validate: the chosen slug MUST exist in the topology; otherwise fall
   back to the rule-based recommendation.
4. Map both AI and rules results into a single `QueueSuggestion` shape with a
   `source` discriminator (`"ai"` | `"rules"`).
5. Expose via `POST /queues/suggestion`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/queue_suggestion.py` | New | `QueueSuggestionService` + models |
| `src/api/routers/queues.py` | Modified | `POST /queues/suggestion` |
| `tests/test_queue_suggestion.py` | New | Unit tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM returns invalid/hallucinated queue | High | Validate slug vs topology; fallback to rules |
| LLM unavailable in prod (no OpenRouter key, no Ollama) | High | Deterministic rule-based fallback (`source="rules"`) |
| Malformed JSON from model | Medium | Tolerant JSON extraction; fallback on parse failure |
| Latency of LLM call | Medium | Endpoint is on-demand (not in the ingestion hot path) |

## Rollback Plan
1. Remove `POST /queues/suggestion` route
2. Delete `QueueSuggestionService`
3. No DB/schema changes to revert

## Dependencies
- **CE-01** (DB-backed topology) — done.

## Success Criteria
- [ ] `QueueSuggestionService.suggest()` returns an AI suggestion when the LLM is available
- [ ] Falls back to rule-based recommendation when LLM errors or returns unknown queue
- [ ] Suggested queue always exists in the topology
- [ ] `POST /queues/suggestion` returns the serialized suggestion
- [ ] Tests cover AI path, fallback path, and validation
