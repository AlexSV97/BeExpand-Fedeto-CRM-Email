# Archive Report: p0-5-soc-operating-modes-and-articles

## Metadata

| Field | Value |
|-------|-------|
| **Change** | p0-5-soc-operating-modes-and-articles |
| **Title** | SOC Operating Modes and Articles |
| **Status** | PASS WITH WARNINGS (verified) |
| **Archived** | 2026-06-17 |
| **Mode** | hybrid (Engram + openspec) |

## Artifact IDs (Engram)

| Artifact | Obs ID | Topic Key |
|----------|--------|-----------|
| Exploration | #911 | sdd/p0-5-soc-operating-modes-and-articles/explore |
| Tasks | #914 | sdd/p0-5-soc-operating-modes-and-articles/tasks |
| Verify Report | #917 | sdd/p0-5-soc-operating-modes-and-articles/verify-report |
| Archive Report | (this) | sdd/p0-5-soc-operating-modes-and-articles/archive-report |

**Note**: Proposal and design artifacts exist ONLY on filesystem (not saved as separate Engram observations).

## Artifacts on Filesystem

All artifacts archived to:
`openspec/changes/archive/2026-06-17-p0-5-soc-operating-modes-and-articles/`

| File | Size | Status |
|------|------|--------|
| proposal.md | ✅ | Archived |
| design.md | ✅ | Archived |
| tasks.md | ✅ | Archived |
| verify-report.md | ✅ | Archived |

## Summary

### Intent
Propagate the SOC operating mode (live|demo|degraded) to the Smart Ticket Queue surface (which was silently dropping the mode) and give Ticket Copilot real Article objects to display instead of an always-empty count.

### What Changed

**Backend** (`backend/src/api/routers/soc.py`):
- Added `operatingMode: str = "demo"` to `TicketQueueResponse`
- Switched `get_ticket_queue` to call `_resolve_tickets_with_mode()` directly
- Added `_articles_for_ticket()` helper generating 1-3 Article objects per synthetic ticket with realistic content

**Frontend**:
- Added `operatingMode?: string` to `TicketQueueView` interface + normalizer (`ticketQueue.ts`)
- Added operating mode badge (Live/Demo/Degraded) to `SmartTicketQueueSurface.tsx`

### Verification Results
- **8/8** spec scenarios compliant
- **10 tests** across 3 test files (backend integration, frontend normalizer unit, frontend surface integration)
- All implementation tasks (5/5) complete and verified
- CRITICAL: Missing apply-progress artifact (process gap, not code defect)

### Specs Synced
No formal spec files exist under `openspec/specs/` - the change modified existing behavior without creating delta specs. No merge was needed.

### Verification Verdict
**PASS WITH WARNINGS** - implementation complete and correct, all functional requirements met and verified by passing tests.

## SDD Cycle Complete
The change has been fully planned, designed, implemented, verified, and archived.
