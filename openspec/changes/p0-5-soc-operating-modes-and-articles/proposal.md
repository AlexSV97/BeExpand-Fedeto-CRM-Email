# Proposal: SOC Operating Modes and Articles

## Intent

Propagate the SOC operating mode (live|demo|degraded) to ALL surfaces — currently only CommandCenter, SLA War Room, and Reports expose it. Smart Ticket Queue silently drops the mode. Simultaneously, give Ticket Copilot real Article objects to display instead of an always-empty count.

## Scope

### In Scope
- Add `operatingMode` to `TicketQueueResponse` backend model
- Switch `get_ticket_queue` to use `_resolve_tickets_with_mode()`
- Add `operatingMode` to `TicketQueueView` frontend normalizer
- Show operating mode badge in `SmartTicketQueueSurface` (consistent with `CommandCenterSurface`)
- Add synthetic `Article` objects to `_synthetic_tickets()`
- Save exploration + proposal to Engram

### Out of Scope
- OTRS/Znuny healthcheck endpoint (deferred)
- Real OTRS article ingestion (requires OTRS connection)
- Non-SOC surfaces (Account, CRM, etc.)

## Capabilities

> No existing specs under `openspec/specs/`. SOC surfaces tracked informally.

### New Capabilities
None — these fill gaps in existing SOC surfaces.

### Modified Capabilities
- `soc-router`: Add `operatingMode` to ticket queue endpoint response.
- `soc-surfaces`: Add operating mode badge to SmartTicketQueue, real articles to TicketCopilot.

## Approach

1. **Backend**: Add `operatingMode: str = "demo"` to `TicketQueueResponse` (soc.py:419). Change `get_ticket_queue` (soc.py:770) to call `_resolve_tickets_with_mode()` instead of `_resolve_tickets()`. Add Article generation to `_synthetic_tickets()` — 2–3 articles per ticket with varied authors and realistic timestamps.
2. **Frontend**: Add `operatingMode` to `TicketQueueView` in `ticketQueue.ts`. Reuse operating mode badge pattern from `CommandCenterSurface` (lines 587–601) in `SmartTicketQueueSurface`. Articles flow through existing `TicketCopilotResponse` → `normalizeTicketCopilot` pipeline without changes.
3. **Verify**: `py_compile` for Python, TypeScript build for frontend.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/api/routers/soc.py` | Modified | TicketQueueResponse + get_ticket_queue + _synthetic_tickets |
| `backend/src/domain/ticketing.py` | — | No changes needed (Article model exists) |
| `frontend/.../normalize/ticketQueue.ts` | Modified | Add operatingMode to view + normalizer |
| `frontend/.../SmartTicketQueueSurface.tsx` | Modified | Add operating mode badge |
| `frontend/.../TicketCopilotSurface.tsx` | — | Receives articles automatically |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Operating mode badge breaks layout | Low | Add above filter bar, same pattern as CommandCenter |
| Synthetic articles inflate articleCount | Low | Generate 0–3 per ticket, realistic timestamps |

## Rollback Plan

- Backend: Revert `TicketQueueResponse`, revert `get_ticket_queue` to `_resolve_tickets()`, strip `_synthetic_tickets` article generation.
- Frontend: Revert `ticketQueue.ts` normalizer, revert `SmartTicketQueueSurface.tsx`.

## Dependencies

- None — all changes are self-contained.

## Success Criteria

- [ ] `get_ticket_queue` response includes `operatingMode` field
- [ ] SmartTicketQueueSurface shows operating mode badge (live|demo|degraded)
- [ ] `_synthetic_tickets()` generates Ticket objects with 1–3 Article objects each
- [ ] TicketCopilotSurface displays non-zero `articleCount`
- [ ] Python and TypeScript compile without errors
