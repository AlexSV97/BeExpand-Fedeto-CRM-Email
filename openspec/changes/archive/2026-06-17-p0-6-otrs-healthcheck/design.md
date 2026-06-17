# Design: OTRS Healthcheck & Connectivity

## Technical Approach
Extend existing /api/v1/health endpoint with real per-service probes. Add health_check() to OtrsZnunyClient. Surface results in CommandCenter.

## Architecture Decisions

### Decision: Healthcheck endpoint location
**Choice**: Extend existing /api/v1/health (not create /soc/health)
**Rationale**: Health is infrastructure-level, not SOC-specific. One endpoint for all probes.

### Decision: OTRS probe target
**Choice**: GET /api/v1/queues with limit=1
**Rationale**: Lightweight read-only call that confirms auth + connectivity without side effects.

### Decision: DB check
**Choice**: SELECT 1 via SQLAlchemy db.execute(text("SELECT 1"))
**Rationale**: Confirms real DB connectivity, not just driver loaded.

## Data Flow
`
GET /api/v1/health
  ├── DB: execute("SELECT 1") → ok | error
  ├── OTRS: client.health_check() → GET /api/v1/queues?limit=1 → ok | error | not_configured
  └── AI: ping Ollama/OpenRouter → ok | error | not_configured
  └── Response: { status: "ok"|"degraded", services: { database, otrs, ai } }

GET /soc/config
  └── Now includes otrs_configured, otrs_base_url (masked), otrs_queue

Command Center
  └── Shows OTRS connectivity as part of operating mode or separate indicator
`

## File Changes
| File | Action | Description |
|------|--------|-------------|
| backend/src/integrations/otrs_znuny/client.py | Modify | Add health_check() async method |
| backend/src/api/main.py | Modify | Expand /api/v1/health with DB + OTRS + AI probes |
| backend/src/api/routers/soc.py | Modify | Add OTRS status to CommandCenterResponse or add to /soc/config |
| frontend/src/pages/soc/CommandCenterSurface.tsx | Modify | Add OTRS connectivity indicator |

## Testing Strategy
| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | OtrsZnunyClient.health_check() | Mock httpx transport, test ok/error/not_configured |
| Integration | /api/v1/health response shape | Test response has services dict with 3 keys |
| Unit | /soc/config OTRS fields | Test is_configured appears in response |

## Migration
No migration required. New fields added to existing endpoints. Old fields preserved.
