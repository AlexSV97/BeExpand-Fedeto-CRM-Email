# Email to Ticket Ingestion — Specification

## Purpose

Define how classified emails are converted into OTRS tickets with correct queue, priority, and state, as a non-blocking step in the ActionExecutor pipeline.

## Requirements

### Requirement: Category-to-Queue Mapping

The system MUST map email categories to OTRS queues via a configurable data structure (dict or class variable).

| Category | Queue |
|----------|-------|
| `cliente` | Support |
| `lead` | Ventas |
| `proveedor` | Proveedores |

Unknown categories MUST fall back to `OtrsZnunySettings.default_queue` ("Support"). The `nulo` category MUST NOT produce a ticket.

#### Scenario: Known category maps to correct queue

- GIVEN an email classified as "cliente" with urgency "alta"
- WHEN the system maps category to queue
- THEN the resulting queue MUST be "Support"

#### Scenario: Unknown category falls back to default queue

- GIVEN an email classified as "legal" (not in the mapping table)
- WHEN the system maps category to queue
- THEN the resulting queue MUST be "Support" (the configured default)

### Requirement: Urgency-to-Priority Mapping

The system MUST map email urgency to OTRS ticket priority via a configurable data structure.

| Urgency | Priority |
|---------|----------|
| `alta` | HIGH |
| `media` | NORMAL |
| `baja` | LOW |

Missing or unmapped urgency MUST default to `TicketPriority.NORMAL`.

#### Scenario: Alta urgency → HIGH priority

- GIVEN an email with urgency "alta"
- WHEN the system maps urgency to priority
- THEN the resulting priority MUST be HIGH

#### Scenario: Media urgency → NORMAL priority

- GIVEN an email with urgency "media"
- WHEN the system maps urgency to priority
- THEN the resulting priority MUST be NORMAL

#### Scenario: Baja urgency → LOW priority

- GIVEN an email with urgency "baja"
- WHEN the system maps urgency to priority
- THEN the resulting priority MUST be LOW

### Requirement: Ticket State for Incoming Emails

All email-originated tickets MUST be created with state `TicketState.NEW`.

#### Scenario: New ticket state

- GIVEN any classified email that produces a ticket
- WHEN the ticket is created
- THEN the ticket state MUST be NEW

### Requirement: Ticket Creation as Pipeline Step

`ActionExecutor.execute_all()` MUST include OTRS ticket creation as an action positioned after invoice processing, producing an `ActionResult` in `ctx.actions`.

#### Scenario: Ticket created successfully

- GIVEN a classified email with complete data
- WHEN `execute_all()` runs
- THEN an `ActionResult` with `action="otrs_ticket_create"` and `success=True` MUST be appended to `ctx.actions`
- AND the ticket MUST include the email subject, body, sender info, and AI summary as article text

### Requirement: Skip When OTRS Not Configured

If `OtrsZnunySettings.is_configured` returns `False`, the system MUST skip ticket creation and continue the pipeline without error.

#### Scenario: OTRS not configured

- GIVEN OTRS/Znuny is not configured (no `base_url` or no `api_token`)
- WHEN `execute_all()` runs
- THEN no OTRS API call is made
- AND an `ActionResult` with `action="otrs_ticket_create"`, `success=True`, and `detail="OTRS no configurado — omitido"` MUST be appended
- AND the pipeline MUST continue normally

### Requirement: Graceful Degradation on OTRS Failure

If the OTRS API call fails (timeout, connection error, HTTP error), the system MUST log a warning and continue the pipeline.

#### Scenario: OTRS API fails

- GIVEN the OTRS API is unreachable or returns an error
- WHEN the ticket creation step runs
- THEN an `ActionResult` with `action="otrs_ticket_create"` and `success=False` MUST be appended
- AND a warning MUST be logged with the error details
- AND the pipeline MUST continue without aborting other actions

### Requirement: Logging of Ticket Creation Result

The system MUST log each ticket creation attempt with success/failure status and, on success, the OTRS ticket ID.

#### Scenario: Ticket ID logged on success

- GIVEN a ticket is created successfully
- WHEN the system logs the result
- THEN the log entry MUST include the OTRS ticket ID returned by the API

## Non-Functional Requirements

### NFR-1: Pipeline Isolation

OTRS failures MUST NOT block or alter any other action in the pipeline: DB save, CRM sync, email forward, WhatsApp notification, or invoice processing.

### NFR-2: Mapping Configurability

The category→queue and urgency→priority mapping tables MUST be defined as modifiable data structures (Python dict or class variable), not hardcoded conditionals. Changing a mapping MUST NOT require modifying pipeline logic.

### NFR-3: Backward Compatibility

All existing tests MUST continue to pass. The ticket creation step is additive and MUST NOT alter the behavior or outcome of existing actions.

## Out of Scope

- Ticket deduplication (covered by IN-05)
- Auto-response to sender (covered by IN-06)
- Frontend changes (ticket list view, settings UI)
- OTRS settings configuration page
- Email-to-ticket threading or conversation linking
