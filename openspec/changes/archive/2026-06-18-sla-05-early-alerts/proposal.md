# Proposal: SLA-05 — Generar alertas tempranas

## Intent

Backlog story SLA-05 (Épica 3): "Se notifica antes de vencimiento a
analista/coordinación". The SLA building blocks exist — `TicketLifecycleService`
computes remaining time and risk (SLA-01..04) and `GET /soc/sla` is the War Room
(SLA-06) — but nothing proactively **raises and persists an early-warning alert**
before a ticket breaches its SLA. This adds detection, idempotent persistence,
notification and an alerts API.

## Scope

### In Scope
- `SlaAlertService`: scan tickets, detect at-risk ones (watch/high/critical),
  generate alerts, persist them (`record_kind="sla_alert"`), idempotently
- Best-effort notification to analyst/coordination via the existing notifier
- Endpoints: scan, list active, acknowledge
- Unit + endpoint tests

### Out of Scope
- New DB table / migration (reuse `OperationalRecord`)
- A scheduler/cron that auto-runs the scan (scan is on-demand/triggerable;
  wiring it to the auto-sync loop is a follow-up)
- New notification channels (reuse Telegram/WhatsApp notifiers)

## Capabilities

### New Capabilities
- `sla-early-alerts`: proactive pre-breach SLA alerts with persistence + notify

### Modified Capabilities
- none (additive endpoints; reuses `TicketLifecycleService`)

## Approach
1. `SlaAlertService(db, lifecycle, notifier=None)` assesses each ticket with an SLA.
2. For risk ∈ {watch, high, critical} generate an alert; **dedup**: skip if an
   unacknowledged alert at the same-or-higher risk already exists for the ticket.
3. Persist new alerts; best-effort notify (high/critical).
4. Endpoints: `POST /soc/sla/alerts/scan`, `GET /soc/sla/alerts`,
   `POST /soc/sla/alerts/{id}/ack`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/services/sla_alerts.py` | New | `SlaAlertService` + models |
| `src/api/routers/soc.py` | Modified | scan / list / ack endpoints |
| `tests/test_sla_alerts.py` | New | Unit + endpoint tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Alert spam on repeated scans | High | Idempotent dedup per ticket/risk level |
| Notifier failure | Medium | Best-effort: never raise |
| No SLA on a ticket | Low | Skipped (no assessment) |

## Rollback Plan
1. Remove the alerts endpoints
2. Delete `SlaAlertService`
3. No schema changes (records remain inert)

## Dependencies
- **SLA-01..04** (`TicketLifecycleService`) — done. **CE-04** recording pattern — done.

## Success Criteria
- [ ] Scan generates alerts for at-risk tickets (watch/high/critical)
- [ ] Re-scanning does not duplicate alerts at the same risk level
- [ ] Escalating risk (watch→high) produces a new alert
- [ ] Alerts are listable and acknowledgeable
- [ ] Notification is best-effort; existing tests keep passing
