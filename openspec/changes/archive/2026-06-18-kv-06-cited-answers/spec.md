# Knowledge Cited Answers — KV-06 Spec

## Purpose

Generate a grounded answer to a question from the Knowledge Vault that always
references the source documents it used (RAG with mandatory citations).

## Requirements

### REQ-1: KnowledgeAnswerService

A `KnowledgeAnswerService` MUST accept a `KnowledgeVaultService` and an optional
`LLMClient`, and expose `answer(query, limit=4) -> KnowledgeAnswer`. It MUST NOT
raise.

### REQ-2: Retrieve then ground

`answer()` MUST retrieve candidate documents via `vault.search_rag` and build the
answer ONLY from the retrieved documents. The returned `sources` MUST list the
documents used, each with a citation ref, id, title and excerpt.

### REQ-3: AI answer cites sources

When the LLM is available, the answer MUST be generated from a prompt containing
the numbered sources, instructing the model to cite `[n]` and use only those
sources. The result MUST have `source="ai"` and `grounded=True`.

### REQ-4: Deterministic extractive fallback

If the LLM is unavailable, errors, or returns empty, `answer()` MUST return a
deterministic extractive answer built from the top sources' excerpts with `[n]`
citations, `source="extractive"`, `grounded=True`.

### REQ-5: No sources → no fabrication

If retrieval returns no documents, `answer()` MUST return `grounded=False`, an
empty `sources` list, and a message stating no information was found. It MUST NOT
invent sources or content.

### REQ-6: Endpoint

`POST /search/knowledge/answer` MUST accept `{query, limit?}`, require
authentication, and return the `KnowledgeAnswer`.

## Scenarios

### Scenario 1: AI answer cites retrieved sources

- GIVEN a vault with documents matching the query and an available LLM
- WHEN `answer("password reset")` runs
- THEN `source="ai"`, `grounded=True`, and `sources` is non-empty with refs

### Scenario 2: Extractive fallback when LLM unavailable

- GIVEN matching documents but the LLM `generate` raises
- WHEN `answer()` runs
- THEN `source="extractive"`, `grounded=True`, and the answer text contains a `[1]` citation

### Scenario 3: No documents → not grounded

- GIVEN an empty vault (or no matches)
- WHEN `answer("anything")` runs
- THEN `grounded=False`, `sources == []`, and a "no information" message

### Scenario 4: Sources carry id/title/excerpt

- GIVEN a vault with a known document
- WHEN `answer()` retrieves it
- THEN each source has `ref`, `id`, `title` and a non-empty `excerpt`

### Scenario 5: Endpoint round-trip

- GIVEN an authenticated `POST /search/knowledge/answer {"query":"..."}`
- THEN the response is 200 with `answer` and `sources`

### Scenario 6: Endpoint requires auth

- GIVEN no auth header
- WHEN `POST /search/knowledge/answer` is called
- THEN the response is 401

## Non-functional Requirements

- **NFR-1 (On-policy LLM)**: reuse `LLMClient` (free tier / Ollama).
- **NFR-2 (Fail-safe)**: `answer()` never raises; degrades to extractive.
- **NFR-3 (No hallucinated sources)**: sources are always the retrieved docs.

## Out of Scope

- Multi-turn conversational RAG
- Re-ranking changes
