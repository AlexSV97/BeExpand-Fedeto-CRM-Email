# Proposal: IN-05 — Evitar tickets duplicados

## Intent

Prevent duplicate OTRS tickets when the same email event is processed multiple times. Currently, every pipeline run creates a new ticket — regardless of whether one already exists for that email. This causes noise, confusion, and wasted OTRS resources.

## Scope

### In Scope
- `Email` model: add `otrs_ticket_id: Optional[str]` and `otrs_ticket_created_at: Optional[datetime]`
- `ActionExecutor._create_ticket()`: pre-check Email record for existing `otrs_ticket_id` before calling OTRS; post-save ticket ID after successful creation
- Alembic migration for the 2 new columns
- Tests covering: skip on existing ticket ID, save on first creation, edge case with missing Email record

### Out of Scope
- OTRS-side dedup (search API) — no `search_tickets_by_metadata()` client method
- Content fingerprinting (hash-based dedup) — not needed for MVP
- Frontend changes — pure backend
- Retroactive dedup of existing tickets — affects only new pipeline runs
- Cross-account dedup — scoped to same-email dedup only

## Capabilities

### New Capabilities
- None — existing `email-ticket-ingestion` capability extended with dedup guard

### Modified Capabilities
- `email-ticket-ingestion`: add dedup pre-check before ticket creation; post-create persistence of `otrs_ticket_id`

## Approach

**Local DB tracking** (Approach A from exploration).

1. Add `otrs_ticket_id: Optional[str]` and `otrs_ticket_created_at: Optional[datetime]` to `Email` model
2. In `_create_ticket()`: before calling `service.ingest_email()`, check `Email.otrs_ticket_id`. If populated → return `ActionResult(success=True, detail=f"Ticket {id} ya existe")`
3. After successful ticket creation → update the Email record: set `otrs_ticket_id = ticket.id`, `otrs_ticket_created_at = now()`, commit
4. Generate Alembic migration with `op.add_column()` for both fields
5. Tests: mock `ingest_email()`, assert second call skips; assert Email record is updated after first call

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/db/models.py` | Modified | +2 fields on `Email` model |
| `backend/src/agents/action_executor.py` | Modified | Pre-check + post-save in `_create_ticket()` |
| `backend/alembic/versions/` | New | Migration for new columns |
| `backend/tests/test_action_executor.py` | Modified | 3+ new dedup test cases |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Email without `message_id` | Low | `message_id` is auto-generated in `_save_email()` if missing |
| Pipeline fails before post-save → orphan ticket | Low | OTRS ticket exists without local ref; next run creates duplicate (mitigated by eventual consistency, acceptable for MVP) |
| Local DB loss → full re-ingestion | Low | DB backups; acceptable risk for MVP |

## Rollback Plan

Revert the Alembic migration (`downgrade`) + revert changes to `models.py` and `action_executor.py`. Feature is purely additive — no data loss on rollback.

## Dependencies

- BT-01 (OTRS connector) — done
- BT-03 (normalizer) — done
- IN-01 (email-to-ticket ingestion) — done (provides `_create_ticket()`)

## Success Criteria

- [ ] Same `message_id` processed twice → only 1 OTRS ticket created, second call returns "ya existe"
- [ ] `Email.otrs_ticket_id` is populated after first successful ticket creation
- [ ] All existing pipeline tests still pass
