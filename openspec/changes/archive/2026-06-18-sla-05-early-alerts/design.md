# Design: SLA-05 — Generar alertas tempranas

## Technical Approach

`SlaAlertService` assesses tickets via `TicketLifecycleService`, raises alerts for
at-risk tickets (watch/high/critical), and persists them as `OperationalRecord`
rows (`record_kind="sla_alert"`) with idempotent dedup keyed by ticket + risk
level. Notification reuses the existing notifier (Telegram/WhatsApp) best-effort.
SOC endpoints trigger a scan, list active alerts, and acknowledge them. No new
table; mirrors CE-04/CE-05/CE-06 recording patterns.

## Architecture Decisions

### Decision: Idempotent dedup keyed by ticket + risk rank

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Skip if unacknowledged alert ≥ current risk exists | No spam; risk escalation still alerts | **Chosen** |
| One alert per ticket ever | Misses escalation watch→high | Rejected |
| Alert every scan | Spam | Rejected |

### Decision: On-demand scan vs scheduler

The scan is exposed as an endpoint (and callable from the auto-sync loop later).
Wiring an automatic cron is out of scope to keep the change focused.

### Decision: Reuse notifier as-is

The Telegram/WhatsApp notifiers expose `enabled` + `send_alert(...)`. SLA-05 maps
an alert into `send_alert` (subject=message, urgency from risk) best-effort; it is
optional and gated by `enabled`.

## Data Flow

```
POST /soc/sla/alerts/scan
        │ tickets = _resolve_tickets_with_mode(otrs)
        ▼
SlaAlertService(db, lifecycle, notifier).scan(tickets)
   for t with SLA: a = lifecycle.assess(t)
      if risk in {watch,high,critical} and not deduped:
          persist OperationalRecord(record_kind="sla_alert", status=severity, payload=...)
          if risk in {high,critical}: notifier.send_alert(...)  # best-effort
        ▲
GET /soc/sla/alerts → list_active()        POST .../{id}/ack → acknowledge()
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/services/sla_alerts.py` | Create | `SlaAlertService` + models |
| `src/api/routers/soc.py` | Modify | scan / list / ack endpoints |
| `tests/test_sla_alerts.py` | Create | Unit + endpoint tests |

## Interfaces / Contracts

```python
SLA_ALERT_RECORD_KIND = "sla_alert"
_RISK_RANK = {"low":0, "watch":1, "high":2, "critical":3}
_SEVERITY = {"watch":"warning", "high":"high", "critical":"critical"}

class SlaAlert(BaseModel):
    id: str
    ticket_id: str
    sla_name: str | None
    risk_level: str
    severity: str
    remaining_minutes: float | None
    message: str
    acknowledged: bool = False
    created_at: str

class SlaAlertScanResponse(BaseModel):
    scanned: int
    generated: int
    alerts: list[SlaAlert]

class SlaAlertListResponse(BaseModel):
    total: int
    alerts: list[SlaAlert]

class SlaAlertService:
    def __init__(self, db, lifecycle: TicketLifecycleService, notifier=None)
    async def scan(self, tickets: list[Ticket]) -> list[SlaAlert]
    async def list_active(self, limit: int = 100) -> list[SlaAlert]
    async def acknowledge(self, alert_id: str, actor: str) -> bool
```

Dedup: query the most recent `sla_alert` for the ticket; skip when it is
unacknowledged and `_RISK_RANK[last] >= _RISK_RANK[current]`. Records use an
explicit microsecond `created_at` for deterministic ordering (as in CE-05/CE-06).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | at-risk raises alert (Sc.1) | craft ticket with old created_at + short SLA |
| Unit | healthy no alert (Sc.2) | fresh ticket |
| Unit | re-scan no dup (Sc.3) | scan twice |
| Unit | risk escalation new alert (Sc.4) | watch then high (monkeypatch assess) |
| Unit | no SLA skipped (Sc.5) | sla=None |
| Unit | acknowledge removes (Sc.6) | ack then list_active |
| Integration | endpoints + auth (Sc.7) | client scan/list; no header → 401 |

## Migration / Rollout

Additive, no schema change. Rollback = remove endpoints + service.

## Open Questions

- [ ] ¿Disparar el scan automáticamente desde `_auto_sync_loop`? Se deja como
  follow-up; el endpoint permite integrarlo o invocarlo desde un cron.
