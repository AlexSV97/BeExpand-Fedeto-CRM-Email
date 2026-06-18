# Observability Snapshot — RP-04 Spec

## Purpose

Provide a single observability view of the system: integration health, operating
mode, activity counts and failures, and background-job intervals — built from real
data without external network calls.

## Requirements

### REQ-1: ObservabilityService

An `ObservabilityService` MUST accept an `AsyncSession` and expose
`snapshot() -> ObservabilitySnapshot`. It MUST NOT perform external network calls
(no live OTRS/LLM probes); status is derived from configuration + DB reachability.

### REQ-2: Integration status

The snapshot MUST include integration statuses for `database` (ok when the DB
query succeeds), `otrs` (`configured`/`not_configured` from `OtrsZnunySettings`),
and `ai` (`openrouter` when an OpenRouter key is set, else `ollama-local`).

### REQ-3: Operating mode

The snapshot MUST include `operatingMode`: `live` when OTRS is configured, else
`demo`.

### REQ-4: Activity counts and failures

The snapshot MUST include `recordCounts` (count of `OperationalRecord` grouped by
`record_kind`) and `failures` (count of records whose status denotes a failure,
e.g. `failure`/`error`).

### REQ-5: Job intervals

The snapshot MUST include `autoSyncIntervalSeconds` and
`slaAlertScanIntervalSeconds` from settings.

### REQ-6: Endpoint

`GET /reporting/observability` MUST return the snapshot and require authentication.

## Scenarios

### Scenario 1: Snapshot reports integrations and mode

- GIVEN OTRS not configured
- WHEN `snapshot()` runs
- THEN integrations include `database=ok`, `otrs=not_configured`, and `operatingMode="demo"`

### Scenario 2: Record counts reflect stored records

- GIVEN two `OperationalRecord` of kind `escalation` exist
- WHEN `snapshot()` runs
- THEN `recordCounts["escalation"] == 2`

### Scenario 3: Failures counted

- GIVEN an `OperationalRecord` with a failure status exists
- WHEN `snapshot()` runs
- THEN `failures >= 1`

### Scenario 4: Job intervals included

- WHEN `snapshot()` runs
- THEN it includes `autoSyncIntervalSeconds` and `slaAlertScanIntervalSeconds`

### Scenario 5: Endpoint round-trip

- GIVEN an authenticated `GET /reporting/observability`
- THEN the response is 200 with the snapshot shape

### Scenario 6: Endpoint requires auth

- GIVEN no auth header
- WHEN `GET /reporting/observability` is called
- THEN the response is 401

## Non-functional Requirements

- **NFR-1 (No external I/O)**: no live OTRS/LLM probes; fast and deterministic.
- **NFR-2 (No migration)**: reuse `OperationalRecord` and settings.

## Out of Scope

- Real per-request latency and LLM cost metrics (need metrics middleware)
- Metrics exporters (Prometheus/OTel)
