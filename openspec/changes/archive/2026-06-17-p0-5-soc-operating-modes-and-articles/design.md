# Design: SOC Operating Modes and Articles

## Problem

Two gaps in the SOC surfaces:
1. **Smart Ticket Queue** drops the operating mode. `_resolve_tickets()` discards the mode string that `_resolve_tickets_with_mode()` already provides. The frontend never sees `operatingMode`, so the badge can't render.
2. **Ticket Copilot** always shows `articleCount: 0` because `_synthetic_tickets()` creates `Ticket` objects with an empty `articles` list.

## Technical Approach

### Backend — `src/api/routers/soc.py`

**1. `TicketQueueResponse` (line 419)**

Add `operatingMode: str = "demo"` field. Matches the exact pattern used by `CommandCenterResponse` (line 400), `SlaWarRoomResponse` (line 483), and `ReportingResponse` (line 544). Required field with default ensures backward compatibility — existing consumers that don't send it will get `"demo"`.

**2. `get_ticket_queue()` (line 770)**

Current code calls `_resolve_tickets(otrs, 25)`, a thin wrapper that calls `_resolve_tickets_with_mode` but discards the mode:

```python
async def _resolve_tickets(otrs, count=25) -> list[Ticket]:
    tickets, _mode = await _resolve_tickets_with_mode(otrs, count)
    return tickets
```

Change `get_ticket_queue` to call `_resolve_tickets_with_mode` directly, destructure the tuple, and pass the mode:

```python
tickets, operating_mode = await _resolve_tickets_with_mode(otrs, 25)
```

Then include it in the response: `operatingMode=operating_mode`.

The `_resolve_tickets` wrapper becomes dead code but is kept for now since `_resolve_ticket` (singular) still uses it internally. Cleanup deferred.

**3. `_synthetic_tickets()` (line 276)**

Each synthetic `Ticket` currently lacks articles. The `Ticket` model (domain/ticketing.py:167) already supports `articles: list[Article]`. Add 1–3 `Article` objects per ticket using the domain `Article` model.

Article content drawn from a pool aligned with the ticket's subject (e.g., if subject is about "password reset", articles describe the issue, troubleshooting steps, and resolution). Vary `author_kind` between `ActorKind.HUMAN` and `ActorKind.IA` for realism. Timestamps staggered around the ticket's `created_at` / `updated_at`.

### Frontend

**1. `ticketQueue.ts` normalizer**

- Add `operatingMode?: string` to the `TicketQueueView` interface.
- In `normalizeTicketQueue()`, extract from raw: `operatingMode: (raw.operatingMode as string) ?? 'demo'`.
- Matches the exact pattern in `commandCenter.ts` (line 40).

**2. `SmartTicketQueueSurface.tsx`**

- Add operating mode badge between the header and the filter bar section.
- Reuse the exact pattern from `CommandCenterSurface` (lines 587–601): green dot + "Live" for `live`, yellow dot + "Demo" for `demo`, red dot + "Degraded" for `degraded`.
- Pull `operatingMode` from `view.operatingMode` (already normalized).
- No shared component — only 1 surface needs this, inline is fine.

**3. `TicketCopilotSurface.tsx`**

- No changes needed. The `TicketCopilotResponse` already includes `ticketContext.articleCount` and the copilot endpoint already computes it via `len(ticket.articles)`. Once `_synthetic_tickets()` populates articles, non-zero counts flow through automatically.

## Architecture Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| `operatingMode` field type | Optional vs Required | Required with default `"demo"` | Matches existing pattern in 3 other response models |
| Article generation strategy | From Ticket model vs separate endpoint | From `_synthetic_tickets()` | Simpler, no new endpoint, no OTRS dependency |
| Operating mode badge | Shared component vs inline | Inline in surface | Only 1 consumer of the badge, avoid premature abstraction |
| Dead `_resolve_tickets` wrapper | Remove vs keep | Keep | Still referenced indirectly; cleanup deferred to next change |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/api/routers/soc.py` | Modify | Add `operatingMode` to `TicketQueueResponse`; switch `get_ticket_queue` to `_resolve_tickets_with_mode`; add Articles to `_synthetic_tickets` |
| `frontend/.../normalize/ticketQueue.ts` | Modify | Add `operatingMode` to `TicketQueueView` + normalizer |
| `frontend/.../SmartTicketQueueSurface.tsx` | Modify | Add operating mode badge below header |

## Verification

1. `python -m py_compile backend/src/api/routers/soc.py` — no syntax errors
2. Frontend TypeScript build — no type errors
3. Manual: hit `GET /soc/tickets`, confirm `operatingMode` in response
4. Manual: open SmartTicketQueue in browser, confirm badge renders
5. Manual: open TicketCopilot, confirm `articleCount > 0`
