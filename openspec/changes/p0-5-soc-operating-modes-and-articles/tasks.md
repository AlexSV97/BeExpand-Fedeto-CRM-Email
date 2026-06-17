# Tasks: SOC Operating Modes and Articles

## Phase 1: Backend Foundation

- [x] 1.1 Add `operatingMode: str = "demo"` field to `TicketQueueResponse` in `backend/src/api/routers/soc.py` (line 419) � matches CommandCenterResponse pattern
- [x] 1.2 Switch `get_ticket_queue()` (line 770) to call `_resolve_tickets_with_mode(otrs, 25)` and destructure `(tickets, operating_mode)`; pass `operatingMode=operating_mode` in response
- [x] 1.3 In `_synthetic_tickets()` (line 276), import `Article` from `src.domain.ticketing` and append 1�3 `Article` objects per ticket with content aligned to subject, varied `author_kind` (HUMAN/IA), and staggered timestamps

## Phase 2: Frontend Wiring

- [x] 2.1 Add `operatingMode?: string` to `TicketQueueView` interface in `frontend/src/services/soc/normalize/ticketQueue.ts`; extract from raw in `normalizeTicketQueue()` as `operatingMode: (raw.operatingMode as string) ?? 'demo'`
- [x] 2.2 Add operating mode badge to `SmartTicketQueueSurface.tsx` between header and filter bar � reuse exact pattern from `CommandCenterSurface` (lines 587�601): green dot + "Live" for `live`, yellow dot + "Demo" for `demo`, red dot + "Degraded" for `degraded`; read from `view.operatingMode`

## Phase 3: Verification

- [x] 3.1 Run `python -m py_compile backend/src/api/routers/soc.py` � PASS (no syntax/type errors)
- [ ] 3.2 Run `npx tsc --noEmit` on frontend � pre-existing errors in `mockData.ts` (4) and unused variables (3) � NONE caused by our changes
- [ ] 3.3 Manual: hit `GET /soc/tickets` and confirm `operatingMode` in response; open SmartTicketQueue and confirm badge renders; open TicketCopilot and confirm `articleCount > 0`
