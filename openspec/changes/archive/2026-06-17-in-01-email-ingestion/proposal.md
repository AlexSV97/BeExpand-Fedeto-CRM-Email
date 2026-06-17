# Proposal: IN-01 -- Email to Ticket Ingestion

## Intent

Connect the email processing pipeline to OTRS ticket creation so every classified email automatically becomes an OTRS ticket with correct state, queue, and priority.

## Scope

### In Scope
- Add `_create_ticket()` method to `ActionExecutor`, called from `execute_all()`
- Mapping from category to OTRS queue (cliente->Support, lead->Ventas, proveedor->Proveedores, etc.)
- Mapping from urgency to TicketPriority (alta->HIGH, media->NORMAL, baja->LOW)
- State always `TicketState.NEW` for incoming emails
- Use `extracted.summary` as comment/article body in the ticket
- Graceful skip if OTRS not configured (OtrsZnunySettings.is_configured)
- Graceful error handling: log.warning + continue on OTRS failure
- Tests for the new method

### Out of Scope
- Duplicate detection (IN-05 -- separate change)
- Auto-response to sender (IN-06 -- separate change)
- Frontend ticket list view
- OTRS settings UI / configuration page
- Email-to-ticket threading or conversation linking

## Capabilities

### New Capabilities
- `email-ticket-ingestion`: automatic conversion of classified emails into OTRS tickets with queue/priority/state mapping

### Modified Capabilities
- None -- pure extension of existing pipeline; no spec-level behavior changes

## Approach

Add `_create_ticket()` as action **number 6** in `ActionExecutor.execute_all()`. Build a `TicketIngestionInput` from the `EmailContext` (subject, body, sender, category->queue, urgency->priority), then call `TicketIngestionService.ingest_email()`. Wrap in try/except: failure logs a warning and produces an `ActionResult(success=False)` -- never breaks the pipeline. Guard with `OtrsZnunySettings.is_configured` so environments without OTRS skip cleanly.

Uses existing models (`TicketIngestionInput`, `TicketCreateRequest`) and existing service (`TicketIngestionService`). No new dependencies.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/agents/action_executor.py` | Modified | Add `_create_ticket()` + call in `execute_all()` |
| `backend/tests/agents/test_action_executor.py` | Modified | Add tests for ticket creation, mapping, and OTRS failure |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OTRS unavailable | Medium | Graceful skip + warning log; pipeline continues |
| Queue name mismatch | Low | Configurable mapping dict; test with each category |
| Pipeline latency increase | Low | OTRS call is async; no blocking |

## Rollback Plan

Revert the two files changed (action_executor.py + test file). The pipeline continues working -- ticket creation is additive.

## Dependencies

- BT-01 (OTRS connector) -- done
- BT-03 (normalizer) -- done
- `TicketIngestionService` + `OtrsZnunyClient` -- already tested with `FakeOtrsConnector`

## Success Criteria

- [ ] An email that completes the pipeline results in an `ActionResult` with action `otrs_ticket_create` and `success=True`
- [ ] The created ticket has correct queue (mapped from category), priority (mapped from urgency), and state=NEW
- [ ] Pipeline continues gracefully if OTRS is down or not configured
- [ ] All existing pipeline tests still pass
