# Design: CP-05 / CP-06 — Borradores de respuesta y nota interna

## Technical Approach

`TicketDraftService` builds a prompt from the ticket (subject, customer, recent
articles) and calls `LLMClient.generate` to produce a customer reply (CP-05) or an
internal note (CP-06). Any failure or empty output degrades to a deterministic
template (`source="template"`). Drafts carry `requires_approval=True` and are never
sent (CP-07). Exposed via `POST /soc/tickets/{id}/draft`. Mirrors CE-02's
AI-with-fallback pattern; no DB/schema change.

## Architecture Decisions

### Decision: New ticket-scoped service vs reuse ReplySuggesterAgent

| Option | Tradeoff | Decision |
|--------|----------|----------|
| New `TicketDraftService(ticket)` | Works from a `Ticket`; supports both reply + note | **Chosen** |
| Reuse `ReplySuggesterAgent(EmailContext)` | Email-pipeline shaped; needs an EmailContext adapter | Rejected (impedance mismatch) |

### Decision: Template fallback over hard failure

Prod often has no reachable LLM; a deterministic template keeps the feature usable
and on-policy (free-tier + rules), consistent with CE-02.

## Data Flow

```
POST /soc/tickets/{id}/draft?kind=...
   ticket = _resolve_ticket(otrs, id)
   TicketDraftService().draft(ticket, kind)
      prompt(subject, customer, last articles) → LLMClient.generate
        ok → DraftResult(source="ai")
        error/empty → DraftResult(source="template")
   requires_approval=True (never sent)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/ticket_drafts.py` | Create | `TicketDraftService` + `DraftResult` |
| `src/api/routers/soc.py` | Modify | `POST /soc/tickets/{id}/draft` |
| `tests/test_ticket_drafts.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
DraftKind = Literal["customer_reply", "internal_note"]

class DraftResult(BaseModel):
    ticket_id: str
    kind: DraftKind
    source: Literal["ai", "template"]
    text: str
    requires_approval: bool = True
    model: str | None = None

class TicketDraftService:
    def __init__(self, llm_client: LLMClient | None = None)
    async def draft(self, ticket: Ticket, kind: DraftKind) -> DraftResult
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | AI reply (Sc.1) | FakeLLM returns text → source ai |
| Unit | internal note kind (Sc.2) | kind passthrough |
| Unit | fallback on raise (Sc.3) | RaisingLLM → source template |
| Unit | fallback on empty (Sc.4) | FakeLLM("") → template |
| Integration | endpoint (Sc.5) | client → 200 (template, LLM unreachable) |
| Integration | invalid kind 422 (Sc.6) | bad kind |
| Integration | auth (Sc.7) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoint + service.

## Open Questions

- [ ] ¿Persistir borradores (historial) o adjuntarlos como nota interna tras
  aprobación? Fuera de alcance; el envío/persistencia es un paso humano posterior.
