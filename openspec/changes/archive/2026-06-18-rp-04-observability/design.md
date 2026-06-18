# Design: RP-04 — Dashboard de observabilidad

## Technical Approach

`ObservabilityService.snapshot()` aggregates a system view from data already
available — integration status (config + DB reachability), derived operating
mode, `OperationalRecord` activity counts/failures, and job intervals from
settings — with no external network calls (deterministic, fast). Exposed via
`GET /reporting/observability`. Real latency/cost metrics are explicitly deferred
(need metrics middleware).

## Architecture Decisions

### Decision: Config/DB-derived status vs live probes

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Status from config + DB query | Fast, deterministic, no flaky network | **Chosen** |
| Live OTRS/LLM probes | Real-time but slow/flaky; `/api/v1/health` already does live probes | Rejected here |

### Decision: Activity from OperationalRecord group-by

The system already records escalations, ownership, sla_alerts, agent
recommendations/approvals, audit events as `OperationalRecord`. Grouping by
`record_kind` gives a real activity view for free.

## Data Flow

```
GET /reporting/observability
   ObservabilityService(db).snapshot()
     integrations: database(ok) + otrs(OtrsZnunySettings.is_configured) + ai(openrouter|ollama)
     operatingMode: live if otrs configured else demo
     recordCounts: SELECT record_kind, count(*) GROUP BY record_kind
     failures: count(status in {failure,error})
     intervals: settings.sync_interval_seconds, settings.sla_alert_scan_interval_seconds
   → ObservabilitySnapshot
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/observability.py` | Create | `ObservabilityService` + models |
| `src/api/routers/reporting.py` | Modify | `GET /reporting/observability` |
| `tests/test_observability.py` | Create | Unit + endpoint |

## Interfaces / Contracts

```python
class IntegrationStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None

class ObservabilitySnapshot(BaseModel):
    generatedAt: str
    operatingMode: str            # live | demo
    integrations: list[IntegrationStatus]
    recordCounts: dict[str, int]
    failures: int
    autoSyncIntervalSeconds: int
    slaAlertScanIntervalSeconds: int

class ObservabilityService:
    def __init__(self, db: AsyncSession)
    async def snapshot(self) -> ObservabilitySnapshot
```

Failure statuses considered: `{"failure", "error"}` (case-insensitive).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | integrations + mode (Sc.1) | OTRS unconfigured → demo, otrs not_configured |
| Unit | record counts (Sc.2) | seed 2 escalation records → count 2 |
| Unit | failures (Sc.3) | seed a failure-status record → failures>=1 |
| Unit | intervals (Sc.4) | snapshot includes both intervals |
| Integration | endpoint (Sc.5) | client → 200 + shape |
| Integration | auth (Sc.6) | no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoint + service.

## Open Questions

- [ ] Latencia/coste reales → requieren middleware de métricas + tracking de uso
  LLM; siguiente iteración (RP-04 fase 2).
