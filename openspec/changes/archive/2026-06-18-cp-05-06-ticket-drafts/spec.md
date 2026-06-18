# Ticket Drafts — CP-05 / CP-06 Spec

## Purpose

Generate AI-assisted drafts for a ticket — a customer reply (CP-05) and an
internal note (CP-06) — to speed up analyst responses, with a deterministic
fallback and mandatory human approval before sending (CP-07).

## Requirements

### REQ-1: TicketDraftService

A `TicketDraftService` MUST expose `draft(ticket, kind)` where `kind` is
`customer_reply` or `internal_note`, returning a `DraftResult` with
`source` (`ai`|`template`), `text`, `kind`, `ticket_id` and `requires_approval`.

### REQ-2: AI generation with context

`draft()` MUST build a prompt from the ticket (subject, customer, recent
articles) and call `LLMClient.generate`. A non-empty LLM response yields
`source="ai"`.

### REQ-3: Deterministic fallback

If the LLM is unavailable, raises, or returns empty, `draft()` MUST return a
non-empty template draft with `source="template"`. `draft()` MUST never raise.

### REQ-4: Approval required

Every `DraftResult` MUST have `requires_approval=True`; the service MUST NOT send
the draft anywhere (write-only).

### REQ-5: Endpoint

`POST /soc/tickets/{id}/draft?kind=customer_reply|internal_note` MUST return the
`DraftResult`, require authentication, validate `kind` (→ 422 otherwise), and 404
when the ticket is unknown.

## Scenarios

### Scenario 1: AI customer reply

- GIVEN an LLM that returns a draft
- WHEN `draft(ticket, "customer_reply")` runs
- THEN `source="ai"` and `text` is the LLM output, `requires_approval=True`

### Scenario 2: Internal note kind

- GIVEN `kind="internal_note"`
- WHEN `draft()` runs
- THEN `kind="internal_note"` in the result

### Scenario 3: Fallback to template when LLM fails

- GIVEN an LLM whose `generate` raises
- WHEN `draft()` runs
- THEN `source="template"` and `text` is non-empty

### Scenario 4: Fallback on empty LLM output

- GIVEN an LLM returning an empty string
- WHEN `draft()` runs
- THEN `source="template"`

### Scenario 5: Endpoint round-trip

- GIVEN `POST /soc/tickets/TICKET-1000/draft?kind=customer_reply`
- THEN 200 with a `DraftResult` (LLM unreachable in tests → `source="template"`)

### Scenario 6: Invalid kind rejected

- GIVEN `kind="nope"`
- THEN the endpoint returns 422

### Scenario 7: Auth required

- GIVEN no auth header
- THEN the endpoint returns 401

## Non-functional Requirements

- **NFR-1 (On-policy LLM)**: Reuse `LLMClient` (free tier / Ollama).
- **NFR-2 (Fail-safe)**: `draft()` never raises; degrades to template.
- **NFR-3 (Human-in-the-loop)**: drafts are never auto-sent.

## Out of Scope

- Sending/writeback of the draft
- Draft persistence/history
