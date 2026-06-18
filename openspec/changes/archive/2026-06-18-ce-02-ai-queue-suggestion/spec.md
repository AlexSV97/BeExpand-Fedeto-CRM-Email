# AI Queue Suggestion — CE-02 Spec

## Purpose

Add an AI-assisted layer that suggests the most appropriate queue for an
incoming ticket/email from the live DB topology (CE-01), returning a confidence
score, a human-readable reason and ranked alternatives. The rule-based
`QueueStrategyService.recommend()` remains as a deterministic fallback so the
feature degrades gracefully when no LLM backend is reachable.

## Requirements

### REQ-1: QueueSuggestionService

A `QueueSuggestionService` MUST accept a `QueueStrategyService` (topology source)
and an optional `LLMClient`. Its `suggest(request)` method MUST return a
`QueueSuggestion` containing a `source` (`"ai"` or `"rules"`), a `recommended`
item and a list of `alternatives`.

### REQ-2: Candidates from the live topology

The service MUST build the candidate queue list from `strategy.topology()`
(roots + special queues). The LLM MUST only be offered queues that exist in the
topology.

### REQ-3: AI suggestion validated against topology

The slug chosen by the LLM MUST be validated against the topology. If the slug
does not match any known queue, the system MUST discard the AI result and fall
back to the rule-based recommendation.

### REQ-4: Deterministic fallback

If the LLM client is unavailable, raises, or returns unparseable output, the
service MUST return a `QueueSuggestion` with `source="rules"` built from
`QueueStrategyService.recommend()`.

### REQ-5: Suggestion endpoint

The system MUST expose `POST /queues/suggestion` that accepts a
`QueueSuggestionRequest` (subject, body_text, optional category, urgency) and
returns a `QueueSuggestion`. The endpoint MUST require authentication, like the
other queue endpoints.

### REQ-6: Confidence bounds

`recommended.confidence` MUST be a float in `[0.0, 1.0]`. AI confidence values
outside the range MUST be clamped.

## Scenarios

### Scenario 1: AI suggests a valid queue

- GIVEN an available LLM that returns `{"slug": "n2-resolucion", "confidence": 0.9, "reason": "..."}`
- WHEN `suggest()` runs for an incident-like ticket
- THEN the result has `source="ai"` and `recommended.queue.slug == "n2-resolucion"`

### Scenario 2: LLM unavailable falls back to rules

- GIVEN an `LLMClient` whose `generate()` raises
- WHEN `suggest()` runs
- THEN the result has `source="rules"` and `recommended` matches `QueueStrategyService.recommend()`

### Scenario 3: LLM returns unknown queue falls back to rules

- GIVEN an LLM that returns `{"slug": "does-not-exist", ...}`
- WHEN `suggest()` runs
- THEN the AI result is discarded and the result has `source="rules"`

### Scenario 4: Malformed JSON falls back to rules

- GIVEN an LLM that returns non-JSON prose
- WHEN `suggest()` runs
- THEN the result has `source="rules"`

### Scenario 5: Endpoint returns serialized suggestion

- GIVEN an authenticated request to `POST /queues/suggestion`
- WHEN a valid `QueueSuggestionRequest` body is posted
- THEN the response is `200` with a JSON `QueueSuggestion` (source, recommended, alternatives)

### Scenario 6: Confidence is clamped

- GIVEN an LLM that returns `confidence: 1.7`
- WHEN `suggest()` runs
- THEN `recommended.confidence == 1.0`

## Non-functional Requirements

- **NFR-1 (No hot-path impact)**: The suggestion is on-demand via the endpoint;
  it MUST NOT be added to the email ingestion pipeline.
- **NFR-2 (On-policy LLM)**: Use the existing `LLMClient` (OpenRouter free tier
  or local Ollama); no paid-credit assumptions.
- **NFR-3 (Fail-safe)**: `suggest()` MUST never raise; any failure degrades to
  the rule-based fallback.

## Out of Scope

- Auto-applying a suggestion to a ticket
- N-level escalation (CE-03), escalation recording (CE-04)
- Embeddings / fine-tuned routing models
