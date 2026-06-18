# SLA Early Alerts — SLA-05 Spec

## Purpose

Proactively detect tickets approaching an SLA breach and raise persisted,
notifiable early-warning alerts, so analysts/coordination are informed before
expiry. Builds on `TicketLifecycleService` (risk/remaining) and reuses the
recording pattern.

## Requirements

### REQ-1: SlaAlertService

A `SlaAlertService` MUST accept an `AsyncSession`, a `TicketLifecycleService`, and
an optional notifier. It MUST expose `scan(tickets)`, `list_active(limit)` and
`acknowledge(alert_id, actor)`. Alerts MUST persist as `OperationalRecord` rows
with `record_kind="sla_alert"`.

### REQ-2: Risk detection

`scan()` MUST assess each ticket that has an SLA and consider it at-risk when its
`risk_level` is `watch`, `high` or `critical`. Tickets without an SLA MUST be
skipped.

### REQ-3: Idempotent dedup

For a given ticket, `scan()` MUST NOT create a new alert if an unacknowledged
alert already exists at the same or higher risk level. A higher risk level than
the last alert MUST create a new alert (risk escalation).

### REQ-4: Alert content

Each alert MUST record `resource_id` = ticket id, the `risk_level`, the
`remaining_minutes`, the `sla_name`, a `severity` derived from risk
(`watch→warning`, `high→high`, `critical→critical`), a human message, and the
acknowledged flag (default false).

### REQ-5: Best-effort notification

`scan()` SHOULD notify (analyst/coordination) for `high`/`critical` alerts via the
injected notifier. Notification MUST be best-effort: a failure MUST NOT raise or
prevent persistence.

### REQ-6: Endpoints

The system MUST expose, requiring authentication:
- `POST /soc/sla/alerts/scan` — run a scan over current tickets, return generated alerts
- `GET /soc/sla/alerts` — list active (unacknowledged) alerts
- `POST /soc/sla/alerts/{alert_id}/ack` — acknowledge an alert

### REQ-7: Acknowledge

`acknowledge(alert_id, actor)` MUST mark the alert acknowledged so it no longer
appears in `list_active` and no longer suppresses new alerts of the same level.

## Scenarios

### Scenario 1: Scan raises alert for at-risk ticket

- GIVEN a ticket whose SLA risk is `high`
- WHEN `scan([ticket])` runs
- THEN one `sla_alert` record is created with `severity="high"`

### Scenario 2: Healthy ticket raises no alert

- GIVEN a ticket whose SLA risk is `low`
- WHEN `scan([ticket])` runs
- THEN no alert is created

### Scenario 3: Re-scan does not duplicate

- GIVEN a `high` ticket already alerted (unacknowledged)
- WHEN `scan([ticket])` runs again
- THEN no second alert is created

### Scenario 4: Risk escalation creates a new alert

- GIVEN a ticket previously alerted at `watch`
- WHEN it is re-scanned at `high`
- THEN a new alert is created

### Scenario 5: Ticket without SLA is skipped

- GIVEN a ticket with `sla=None`
- WHEN `scan([ticket])` runs
- THEN no alert is created

### Scenario 6: Acknowledge removes from active

- GIVEN an active alert
- WHEN `acknowledge(id, actor)` runs
- THEN `list_active()` no longer includes it

### Scenario 7: Endpoints work and require auth

- GIVEN authenticated requests
- WHEN `POST /soc/sla/alerts/scan` then `GET /soc/sla/alerts`
- THEN scan returns generated alerts and the list reflects them; without auth → 401

## Non-functional Requirements

- **NFR-1 (No migration)**: Reuse `OperationalRecord`.
- **NFR-2 (Idempotent)**: Repeated scans with unchanged risk MUST NOT duplicate alerts.
- **NFR-3 (Best-effort notify)**: Notification failures never break the scan.
- **NFR-4 (Isolation)**: `"sla_alert"` records MUST NOT appear in other record-kind queries.

## Out of Scope

- Scheduled auto-scan (cron / auto-sync wiring)
- New notification channels
