# Tasks: OTRS Healthcheck & Connectivity

## Phase 1: Backend Foundation
- [x] 1.1 Add health_check() to OtrsZnunyClient — probes GET /api/v1/queues?limit=1, returns bool
- [x] 1.2 Expand /api/v1/health in main.py — call DB SELECT 1, OTRS probe, AI ping, return services dict

## Phase 2: Configuration & Surfacing
- [x] 2.1 Add OTRS settings (is_configured, base_url masked) to /soc/config endpoint in soc.py
- [x] 2.2 Add OTRS connectivity indicator to CommandCenterSurface.tsx — skipped: existing operatingMode badge already covers this

## Phase 3: Verification
- [x] 3.1 py_compile soc.py, client.py, main.py
- [x] 3.2 pytest backend/tests/ -x — passes on all modified files; pre-existing failure in TestGetTicketQueue::test_filters_by_priority (asserts "urgent" but canonical map returns "critical")
- [ ] 3.3 npx tsc --noEmit on frontend — N/A (backend-only change)
