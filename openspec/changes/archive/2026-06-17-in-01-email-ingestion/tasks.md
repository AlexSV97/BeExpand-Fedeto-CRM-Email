# Tasks: IN-01 — Email to Ticket Ingestion

**Change**: `in-01-email-ingestion`
**Status**: Draft
**Date**: 2026-06-17

---

## Group 1 — Mapping & Core Logic (ActionExecutor)

Implementation tasks that add queue/priority mapping, input building, ticket creation, and pipeline integration to `ActionExecutor`.

---

### T1.1: Add QUEUE_MAP, DEPARTMENT_QUEUE_MAP, and URGENCY_PRIORITY_MAP constants

**Description**: Add three class-level mapping dictionaries to `ActionExecutor`:

1. **`QUEUE_MAP: dict[str, str]`** — Maps `Category` enum values to OTRS queue names:
   - `Category.CLIENTE.value` (`"cliente"`) → `"Support"`
   - `Category.LEAD.value` (`"lead"`) → `"Ventas"`
   - `Category.PROVEEDOR.value` (`"proveedor"`) → `"Proveedores"`

2. **`DEPARTMENT_QUEUE_MAP: dict[str, str]`** — Maps `Department` enum values to OTRS queue names (Tier 2 fallback for unknown categories):
   - `Department.SOPORTE.value` (`"soporte"`) → `"Support"`
   - `Department.COMERCIAL.value` (`"comercial"`) → `"Ventas"`
   - `Department.CONTABILIDAD.value` (`"contabilidad"`) → `"Contabilidad"`
   - `Department.PROVEEDORES.value` (`"proveedores"`) → `"Proveedores"`
   - `Department.DIRECCION.value` (`"direccion"`) → `"Direccion"`
   - `Department.OTRO.value` (`"otro"`) → `"Support"`

3. **`URGENCY_PRIORITY_MAP: dict[str, TicketPriority]`** — Maps `Urgency` enum values to `TicketPriority`:
   - `Urgency.ALTA.value` (`"alta"`) → `TicketPriority.HIGH`
   - `Urgency.MEDIA.value` (`"media"`) → `TicketPriority.NORMAL`
   - `Urgency.BAJA.value` (`"baja"`) → `TicketPriority.LOW`

**Also add**: `_resolve_queue(ctx: EmailContext) -> Queue` method that implements 3-tier fallback:
- **Tier 1**: Lookup `ctx.final_category` in `QUEUE_MAP`
- **Tier 2**: Iterate `ctx.routing.departments` and lookup in `DEPARTMENT_QUEUE_MAP`
- **Tier 3**: Fall back to `OtrsZnunySettings().default_queue` (`"Support"`)

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\src\agents\action_executor.py`

**Dependencies**: None

**Acceptance criteria**:
- [ ] `QUEUE_MAP` is a class-level dict with exactly 3 entries (cliente, lead, proveedor)
- [ ] `DEPARTMENT_QUEUE_MAP` is a class-level dict with exactly 6 entries (all departments)
- [ ] `URGENCY_PRIORITY_MAP` is a class-level dict with exactly 3 entries (alta, media, baja)
- [ ] Keys use `Category`, `Department`, and `Urgency` enum values (not raw strings)
- [ ] `_resolve_queue()` returns correct queue for known category
- [ ] `_resolve_queue()` falls back to department routing for unknown categories
- [ ] `_resolve_queue()` falls back to `OtrsZnunySettings.default_queue` when no match found
- [ ] All existing tests still pass

**TDD requirement**: No (constants and simple mapping; tests in T2.1 verify correctness)

---

### T1.2: Add _build_ticket_input(ctx) method

**Description**: Add `_build_ticket_input(self, ctx: EmailContext) -> TicketIngestionInput` method to `ActionExecutor`. This method constructs a `TicketIngestionInput` instance from the `EmailContext`, applying all field mappings from §3.1 of the design doc:

| EmailContext field | TicketIngestionInput field |
|---|---|
| `ctx.raw.subject` | `input.subject` |
| `ctx.raw.body_plain` | `input.body_text` |
| `ctx.raw.body_html` | `input.body_html` |
| `ctx.raw.sender_name` | `input.sender_name` |
| `ctx.raw.sender_email` | `input.sender_email` |
| `ctx.raw.recipients` | `input.recipients` |
| `ctx.raw.message_id` | `input.message_id` |
| `ctx.raw.received_at` | `input.received_at` |
| `self._resolve_queue(ctx)` | `input.queue` |
| urgency from `ctx.extracted.urgency` (mapped through `URGENCY_PRIORITY_MAP`, default `TicketPriority.NORMAL`) | `input.priority` |
| `TicketState.NEW` | `input.state` (constant) |
| `ctx.extracted.summary` | `input.comment_text` |
| `False` | `input.comment_visible_to_customer` |
| Classification metadata dict (category, confidence, resolution_method, urgency, action_required) | `input.metadata` |

The metadata dict must include:
```python
{
    "category": ctx.final_category,
    "confidence": ctx.final_confidence,
    "resolution_method": ctx.resolution_method,
    "urgency": ctx.extracted.urgency if ctx.extracted else "media",
    "action_required": ctx.extracted.action_required if ctx.extracted else None,
}
```

**Guard**: If `ctx.extracted` is `None`, use defaults for urgency (`"media"`) and omit summary/action_required.

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\src\agents\action_executor.py`
- Plus import `TicketIngestionInput` from `src.domain.ticketing`

**Dependencies**: T1.1 (uses `_resolve_queue` and mapping constants)

**Acceptance criteria**:
- [ ] Returns a valid `TicketIngestionInput` when `ctx` has all fields
- [ ] Subject, body, sender fields pass through correctly
- [ ] Queue is resolved via `_resolve_queue()`
- [ ] Priority is mapped from `ctx.extracted.urgency` via `URGENCY_PRIORITY_MAP`
- [ ] Priority defaults to `TicketPriority.NORMAL` when urgency is missing or unmapped
- [ ] State is always `TicketState.NEW`
- [ ] Comment text is `ctx.extracted.summary` (may be `None`)
- [ ] Comment is not visible to customer (`False`)
- [ ] Metadata contains all 5 classification fields
- [ ] `None` values in metadata are preserved (they will be cleaned by `TicketIngestionService._clean_metadata()`)
- [ ] Gracefully handles `ctx.extracted` being `None`

**TDD requirement**: Yes (write tests first in T2.2, then implement)

---

### T1.3: Add _create_ticket(ctx) method

**Description**: Add `_create_ticket(self, ctx: EmailContext) -> ActionResult` method to `ActionExecutor`. This is the main method for OTRS ticket creation. It must be `async`.

**Behaviour**:
1. **Guard — OTRS not configured**: If `OtrsZnunySettings().is_configured` is `False` → return `ActionResult(action="otrs_ticket_create", success=True, detail="OTRS no configurado — omitido")`
2. **Guard — nulo email**: If `ctx.final_category` is `None` or `Category.NULO.value` → return `ActionResult(action="otrs_ticket_create", success=True, detail="Email nulo — no se crea ticket")`
3. **Build input**: Call `self._build_ticket_input(ctx)` to get a `TicketIngestionInput`
4. **Instantiate service**: Create `TicketIngestionService()` with default args (picks up env vars automatically)
5. **Call OTRS**: `ticket = await service.ingest_email(input)`
6. **Close service**: `await service.aclose()`
7. **Log success**: `logger.info(...)` with ticket ID and queue
8. **Return success**: `ActionResult(action="otrs_ticket_create", success=True, detail=f"Ticket {ticket.id} creado en cola {ticket.queue.name}")`
9. **On any exception**: Catch `Exception`, log `logger.warning(...)`, return `ActionResult(action="otrs_ticket_create", success=False, detail=str(e))`

**Crucial**: NEVER re-raise. Every code path returns an `ActionResult`. The pipeline MUST continue regardless of OTRS failure.

**Imports to add**:
- `from src.services.ticket_ingestion import TicketIngestionService`
- `from src.integrations.otrs_znuny.settings import OtrsZnunySettings`
- `from src.domain.ticketing import TicketIngestionInput, TicketPriority, TicketState, Queue`

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\src\agents\action_executor.py`

**Dependencies**: T1.2 (uses `_build_ticket_input`)

**Acceptance criteria**:
- [ ] Returns `ActionResult(action="otrs_ticket_create", success=True, ...)` with ticket ID and queue on success
- [ ] Returns `ActionResult(action="otrs_ticket_create", success=True, detail="OTRS no configurado — omitido")` when OTRS is not configured
- [ ] Returns `ActionResult(action="otrs_ticket_create", success=True, detail="Email nulo — no se crea ticket")` when category is nulo/missing
- [ ] Returns `ActionResult(action="otrs_ticket_create", success=False, detail=...)` on any OTRS/API exception
- [ ] Logs warning on failure, never re-raises
- [ ] Closes the service via `aclose()`
- [ ] All existing tests still pass

**TDD requirement**: Yes (write tests first in T2.2/T2.3, then implement)

---

### T1.4: Integrate _create_ticket into execute_all() flow

**Description**: Add ticket creation as **step 6** in `ActionExecutor.execute_all()`, after `_process_invoices()` (step 5) and before `ctx.actions = actions`.

Add the following code after the invoice processing block (after line ~105):

```python
# 6. Crear ticket en OTRS (si está configurado)
ticket_action = await self._create_ticket(ctx)
actions.append(ticket_action)
```

This places ticket creation at the end of the pipeline so that local-side effects (DB save, CRM sync, email forward) are committed before reaching out to external infrastructure (OTRS). If OTRS is down, everything else is already done.

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\src\agents\action_executor.py`

**Dependencies**: T1.3 (`_create_ticket` must exist)

**Acceptance criteria**:
- [ ] `_create_ticket(ctx)` is called in `execute_all()` as the 6th action
- [ ] The result is appended to `actions` list
- [ ] `ctx.actions` includes an entry with `action="otrs_ticket_create"` after the pipeline runs
- [ ] Pipeline works correctly when OTRS is configured (ticket created)
- [ ] Pipeline works correctly when OTRS is not configured (skipped gracefully)
- [ ] Pipeline works correctly when OTRS fails (logged, continues)
- [ ] All existing pipeline actions (db_save, crm_sync, whatsapp_alert, email_forward, invoice_process) are unaffected
- [ ] All existing tests still pass

**TDD requirement**: No (wiring only; verified by T2.4 and T2.2)

---

## Group 2 — Tests

Test tasks that verify the new functionality and ensure no regressions.

---

### T2.1: Write tests for queue/priority mapping logic

**Description**: Create a new test file at `backend/tests/test_action_executor.py` and add tests that validate the queue and priority mapping logic in isolation. Use `monkeypatch` to ensure OTRS settings are "configured" during tests.

**Test cases**:

| # | Test Name | What it verifies |
|---|---|---|
| 1 | `test_create_ticket_maps_queue_from_category` | cliente→Support, lead→Ventas, proveedor→Proveedores — each via QUEUE_MAP |
| 2 | `test_create_ticket_falls_back_to_department_queue` | Unknown category + `routing.departments=["soporte"]` → queue = Support |
| 3 | `test_create_ticket_falls_back_to_default_queue` | Unknown category + no routing → queue = Support (OtrsZnunySettings.default_queue) |
| 4 | `test_create_ticket_maps_priority_from_urgency` | alta→HIGH, media→NORMAL, baja→LOW via URGENCY_PRIORITY_MAP |
| 5 | `test_create_ticket_defaults_priority_when_urgency_missing` | No urgency → defaults to NORMAL |

**Test approach**: Use `FakeOtrsConnector` (from `test_ticket_ingestion.py`) injected into `TicketIngestionService`. Patch `OtrsZnunySettings.is_configured` to `True`. Validate the `TicketIngestionInput` fields (queue name, priority) that are passed to the fake.

**Fixtures to create**:
```python
@pytest.fixture(autouse=True)
def _patch_otrs_settings(monkeypatch):
    """Ensure OTRS is 'configured' during tests."""
    monkeypatch.setattr(
        "src.integrations.otrs_znuny.settings.OtrsZnunySettings.is_configured",
        True,
        raising=False,
    )

@pytest.fixture
def sample_context():
    """Build a minimal EmailContext for testing."""
    ...
```

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\tests\test_action_executor.py` (CREATE)

**Dependencies**: T1.1 (mapping constants must exist to test against)

**Acceptance criteria**:
- [ ] All 5 test cases pass
- [ ] Queue mapping tests cover all 3 known categories + unknown + no routing
- [ ] Priority mapping tests cover all 3 urgencies + missing/unknown
- [ ] Tests use `FakeOtrsConnector` (no real HTTP calls)
- [ ] Tests are isolated (each test creates its own context)

**TDD requirement**: N/A (these ARE the tests)

---

### T2.2: Write tests for _create_ticket success path

**Description**: Add tests to `test_action_executor.py` that verify the full `_create_ticket` method succeeds with correct data, including field passthrough, article/comment creation, and pipeline integration.

**Test cases**:

| # | Test Name | What it verifies |
|---|---|---|
| 1 | `test_create_ticket_maps_subject_body_sender` | Email with all fields, category=cliente → `ActionResult.success=True`, detail contains ticket ID |
| 2 | `test_create_ticket_includes_summary_as_comment` | `extracted.summary` present → comment added as internal SYSTEM article, not visible to customer |
| 3 | `test_execute_all_includes_ticket_action` | Full `execute_all()` run → `ctx.actions` includes entry with `action="otrs_ticket_create"` |

**Test approach**: Mock `TicketIngestionService.ingest_email` at the module level (monkeypatch) to return a controlled `Ticket` object. Validate `ActionResult` fields and that OTRS was called with correct parameters.

For test #3, mock the entire `_create_ticket` method or use the fake connector approach to verify that `execute_all()` produces 6 actions (including `otrs_ticket_create`).

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\tests\test_action_executor.py` (append to existing new file)

**Dependencies**: T1.3 (`_create_ticket` exists), T2.1 (fixtures and patterns established)

**Acceptance criteria**:
- [ ] All 3 test cases pass
- [ ] Success test verifies detail string contains ticket ID
- [ ] Comment test verifies `author_kind=SYSTEM` and `is_visible_to_customer=False`
- [ ] Pipeline integration test verifies `ctx.actions[5].action == "otrs_ticket_create"`
- [ ] Pipeline integration test verifies `ctx.actions` length is 6
- [ ] No real HTTP calls are made

**TDD requirement**: N/A (these ARE the tests)

---

### T2.3: Write tests for graceful handling (OTRS not configured, nulo, API failure)

**Description**: Add tests to `test_action_executor.py` that verify the pipeline handles all error/edge cases gracefully without breaking.

**Test cases**:

| # | Test Name | What it verifies |
|---|---|---|
| 1 | `test_create_ticket_skips_when_otrs_not_configured` | `OtrsZnunySettings.is_configured` is `False` → success=True, detail="OTRS no configurado — omitido", no API call |
| 2 | `test_create_ticket_skips_when_category_is_nulo` | `final_category="nulo"` → success=True, detail="Email nulo — no se crea ticket", no API call |
| 3 | `test_create_ticket_handles_otrs_api_error` | OTRS API raises `OtrsZnunyError` (timeout/500) → success=False, warning logged, pipeline continues |

**Test approach**: 
- For "not configured": mock `OtrsZnunySettings.is_configured` to return `False`, assert no service call
- For "nulo": set `ctx.final_category = "nulo"`, assert skip
- For "API error": mock `TicketIngestionService.ingest_email` to raise `OtrsZnunyError("timeout")`, assert `ActionResult(success=False)`

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\tests\test_action_executor.py` (append to existing new file)

**Dependencies**: T1.3 (`_create_ticket` exists), T2.1 (fixtures), T2.2 (test patterns)

**Acceptance criteria**:
- [ ] All 3 test cases pass
- [ ] "OTRS not configured" test verifies NO call to `ingest_email` (mock spy)
- [ ] "Nulo" test verifies NO call to `ingest_email` (mock spy)
- [ ] "API error" test verifies `ActionResult(success=False)`
- [ ] "API error" test verifies a `log.warning` was emitted (use `caplog`)
- [ ] All existing tests still pass

**TDD requirement**: N/A (these ARE the tests)

---

### T2.4: Run full test suite to confirm no regressions

**Description**: Execute the complete test suite and confirm all existing tests continue to pass. The ticket creation step is purely additive and MUST NOT alter behavior of existing actions.

**Run command** (from `backend/`):
```bash
pytest tests/ -v --tb=short
```

Or, if using `poetry`:
```bash
poetry run pytest tests/ -v --tb=short
```

**Acceptance criteria**:
- [ ] All existing tests pass (test_ticket_ingestion.py, test_otrs_znuny.py, conftest-dependent tests, etc.)
- [ ] All new tests pass (test_action_executor.py)
- [ ] No new warnings introduced
- [ ] Coverage of new code is satisfactory

**Dependencies**: T2.2, T2.3 (all new tests exist)

**TDD requirement**: N/A (verification task)

---

## Group 3 — Integration

---

### T3.1: Verify end-to-end pipeline with a test email

**Description**: Perform end-to-end verification that the complete email ingestion pipeline, when fed a real (or simulated) classified email, produces an OTRS ticket with correct attributes.

**Two approaches** (choose one based on environment):

**Approach A — Manual (with OTRS available)**:
1. Set up `OTRS_ZNUNY_BASE_URL` and `OTRS_ZNUNY_API_TOKEN` in `.env`
2. Run the full pipeline: `python -m src.orchestrator.main` (or equivalent entry point)
3. Send a test email with category "cliente" and urgency "alta"
4. Verify in OTRS: ticket created in "Support" queue, priority HIGH, state NEW
5. Verify the internal article contains the AI summary
6. Check the logs for ticket ID

**Approach B — Integration test (preferred)**:
- Add an integration test in `test_action_executor.py` that:
  - Creates a real `ActionExecutor` with an in-memory DB session
  - Builds a full `EmailContext` with all fields populated
  - Calls `execute_all()`
  - Asserts `ctx.actions[-1]` is `otrs_ticket_create` with `success=True`
  - Uses `FakeOtrsConnector` so no real OTRS is needed

**Files to modify**:
- `C:\Users\rjuarcad\Desktop\Aiuken-SOC-Email\backend\tests\test_action_executor.py` (if adding integration test)
- Or `.env` for manual verification

**Dependencies**: T1.4 (pipeline integration), T2.4 (unit tests pass)

**Acceptance criteria**:
- [ ] Email → ticket flow works end-to-end
- [ ] Queue, priority, and state are correct
- [ ] AI summary appears as internal article
- [ ] All unit tests still pass

**TDD requirement**: N/A (verification task)

---

## Execution Order

```
T1.1  (mapping constants + _resolve_queue)
  │
  ▼
T1.2  (_build_ticket_input)
  │
  ▼
T1.3  (_create_ticket)
  │
  ├─────────────────────┐
  ▼                     ▼
T1.4  (execute_all)    T2.1  (mapping tests)
  │                     │
  │                     ▼
  │                   T2.2  (success path tests)
  │                     │
  │                     ▼
  │                   T2.3  (error handling tests)
  │                     │
  └─────────┬───────────┘
            ▼
          T2.4  (regression suite)
            │
            ▼
          T3.1  (e2e verification)
```

**Note**: T2.1 can start in parallel with T1.3 (the mapping constants exist after T1.1). T2.2 and T2.3 depend on T1.3 (the method under test must exist) but are independent of T1.4 (pipeline wiring).
