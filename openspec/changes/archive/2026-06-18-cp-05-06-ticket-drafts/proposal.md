# Proposal: CP-05 / CP-06 — Borradores de respuesta y nota interna

## Intent

Backlog stories CP-05 ("Borrador de primera respuesta") and CP-06 ("Borrador de
actualización interna") of Épica 4. A `ReplySuggesterAgent` exists for the email
pipeline but there is no ticket-scoped copilot draft surface. This adds an
AI-assisted draft generator for a ticket — a customer reply and an internal note
— with a deterministic template fallback, exposed via a copilot endpoint. Drafts
always require human approval before sending (CP-07): the service only writes.

## Scope

### In Scope
- `TicketDraftService`: generate `customer_reply` (CP-05) and `internal_note`
  (CP-06) drafts from a ticket via `LLMClient`, with template fallback
- `POST /soc/tickets/{id}/draft?kind=...` endpoint
- `requires_approval=True` on every draft (CP-07 alignment)
- Unit + endpoint tests

### Out of Scope
- Sending the draft (writeback to OTRS / email) — human-in-the-loop, separate
- Persisting drafts / draft history
- Multi-turn copilot chat (existing copilot endpoint already covers conversation)

## Capabilities

### New Capabilities
- `ticket-drafts`: AI-assisted customer/internal drafts with fallback

### Modified Capabilities
- none (additive endpoint)

## Approach
1. `TicketDraftService.draft(ticket, kind)` builds a prompt from the ticket
   (subject, customer, last articles) and calls `LLMClient.generate`.
2. On LLM error/empty/unavailable → deterministic template (`source="template"`).
3. Endpoint validates `kind`, resolves the ticket, returns the `DraftResult`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/ticket_drafts.py` | New | `TicketDraftService` + `DraftResult` |
| `src/api/routers/soc.py` | Modified | `POST /soc/tickets/{id}/draft` |
| `tests/test_ticket_drafts.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM unavailable in prod | High | Deterministic template fallback (`source="template"`) |
| Draft sent without review | — | `requires_approval=True`; service never sends |
| Invalid kind | Medium | Validated → 422 |

## Rollback Plan
1. Remove the draft endpoint
2. Delete `TicketDraftService`
3. No schema changes

## Dependencies
- `LLMClient` (free-tier/Ollama), KV-02 context (best-effort) — available.

## Success Criteria
- [ ] Draft generated for `customer_reply` and `internal_note`
- [ ] Falls back to a non-empty template when the LLM is unavailable
- [ ] Every draft has `requires_approval=True`
- [ ] Invalid kind → 422; endpoint requires auth
