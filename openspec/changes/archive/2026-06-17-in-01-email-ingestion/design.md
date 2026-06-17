# Design: IN-01 — Email to Ticket Ingestion

**Change**: `in-01-email-ingestion`
**Status**: Draft
**Date**: 2026-06-17

---

## 1. Architecture

### Flow Overview

A new step `_create_ticket()` is added to `ActionExecutor.execute_all()` as **action #6**, after invoice processing. This connects two existing, independently tested components:

```
execute_all()
  ├── 1. _save_to_db()          → ctx.actions[0] = db_save
  ├── 2. _sync_to_crm()         → ctx.actions[1] = crm_sync
  ├── 3. _notify_whatsapp()     → ctx.actions[2] = whatsapp_alert
  ├── 4. _forward_email()       → ctx.actions[3] = email_forward
  ├── 5. _process_invoices()    → ctx.actions[4] = invoice_process
  └── 6. _create_ticket() ★ NEW → ctx.actions[5] = otrs_ticket_create
                                     │
                                     ▼
                            ┌─────────────────────┐
                            │ TicketIngestionInput │ ← mapped from EmailContext
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │TicketIngestionService│
                            │  .ingest_email()    │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  OtrsZnunyClient    │
                            │  .create_ticket()   │
                            └─────────────────────┘
```

The call is fully **non-blocking** to the rest of the pipeline: any failure is caught, logged, and recorded as `ActionResult(success=False)` — the pipeline **never** halts because of OTRS.

### Placement Rationale

Step 6 (after `_process_invoices`) because:
1. It depends on external infrastructure (OTRS) — positioning it after all local-side effects means even if OTRS is down, the email is already saved and forwarded locally.
2. The proposal specifies it as "action number 6" in the sequence.

---

## 2. Component Design

### 2.1 New Method: `ActionExecutor._create_ticket()`

```python
async def _create_ticket(self, ctx: EmailContext) -> ActionResult:
    ...
```

**Signature**: `async def _create_ticket(self, ctx: EmailContext) -> ActionResult`

**Behaviour**:
1. **Guard**: If `OtrsZnunySettings().is_configured` is `False` → return `ActionResult(action="otrs_ticket_create", success=True, detail="OTRS no configurado — omitido")`
2. **Skip nulo**: If `ctx.final_category` is `None` or `Category.NULO.value` → return `ActionResult(action="otrs_ticket_create", success=True, detail="Email nulo — no se crea ticket")`
3. **Build input**: Construct `TicketIngestionInput` from `EmailContext` fields (see §3 Data Design)
4. **Call service**: `await TicketIngestionService().ingest_email(input)`
5. **Record success**: `ActionResult(action="otrs_ticket_create", success=True, detail=f"Ticket {ticket.id} creado en cola {queue_name}")`
6. **On any exception**: log `logger.warning`, return `ActionResult(action="otrs_ticket_create", success=False, detail=str(e))`

**Error handling rule**: NEVER re-raise. Every code path returns an `ActionResult`.

### 2.2 Queue Mapping Table

Defined as a class-level constant on `ActionExecutor`:

| Key (category) | Value (OTRS queue) |
|---|---|
| `"cliente"` | `"Support"` |
| `"lead"` | `"Ventas"` |
| `"proveedor"` | `"Proveedores"` |

```python
# As class constant on ActionExecutor
QUEUE_MAP: dict[str, str] = {
    Category.CLIENTE.value: "Support",
    Category.LEAD.value: "Ventas",
    Category.PROVEEDOR.value: "Proveedores",
}
```

These can be promoted to `Settings` (config.py) later if the business needs runtime-reconfigurable queue names, without changing code.

### 2.3 Priority Mapping Table

Defined as a class-level constant on `ActionExecutor`:

| Urgency string | TicketPriority |
|---|---|
| `"alta"` | `TicketPriority.HIGH` |
| `"media"` | `TicketPriority.NORMAL` |
| `"baja"` | `TicketPriority.LOW` |

```python
# As class constant on ActionExecutor
URGENCY_PRIORITY_MAP: dict[str, TicketPriority] = {
    Urgency.ALTA.value: TicketPriority.HIGH,
    Urgency.MEDIA.value: TicketPriority.NORMAL,
    Urgency.BAJA.value: TicketPriority.LOW,
}
```

### 2.4 State

All incoming emails create tickets with `TicketState.NEW`. This is the service default (`TicketCreateRequest.state = TicketState.NEW`).

### 2.5 Comment / Internal Article

`ctx.extracted.summary` (if non-empty) is passed as `input.comment_text`. The `TicketIngestionService` then calls `build_comment_article()`, which creates an `ArticleDraft` with `author_kind=SYSTEM` and `author_name=OtrsZnunySettings.ai_actor_name` (default: `"BeConnect AI"`). This ensures every ticket has an internal note with the AI-generated summary.

`comment_visible_to_customer` is set to `False` — the summary is an internal analysis note, not visible to the customer.

### 2.6 Metadata

The following classification metadata is added to `input.metadata`:

```python
metadata={
    "category": ctx.final_category,
    "confidence": ctx.final_confidence,
    "resolution_method": ctx.resolution_method,
    "urgency": ctx.extracted.urgency if ctx.extracted else "media",
    "action_required": ctx.extracted.action_required if ctx.extracted else None,
}
```

The `TicketIngestionService._clean_metadata()` method strips `None` values automatically.

---

## 3. Data Design

### 3.1 Field Mapping: `EmailContext` → `TicketIngestionInput`

| EmailContext field | TicketIngestionInput field | Notes |
|---|---|---|
| `ctx.raw.subject` | `input.subject` | Direct pass-through |
| `ctx.raw.body_plain` | `input.body_text` | Primary body content |
| `ctx.raw.body_html` | `input.body_html` | Pass-through (may be None) |
| `ctx.raw.sender_name` | `input.sender_name` | Direct pass-through |
| `ctx.raw.sender_email` | `input.sender_email` | Direct pass-through |
| `ctx.raw.recipients` | `input.recipients` | Pass-through (default `[]`) |
| `ctx.raw.message_id` | `input.message_id` | Pass-through (may be None) |
| `ctx.raw.received_at` | `input.received_at` | Pass-through (may be None) |
| *mapped from category* | `input.queue` | See §4 Queue Routing |
| *mapped from urgency* | `input.priority` | See §2.3 Priority Mapping |
| `TicketState.NEW` | `input.state` | Hardcoded |
| `ctx.extracted.summary` | `input.comment_text` | May be None |
| `False` | `input.comment_visible_to_customer` | Internal note only |
| *classification metadata* | `input.metadata` | See §2.6 |

### 3.2 Result

`TicketIngestionService.ingest_email()` returns a `Ticket` domain model. The method captures:
- `ticket.id` — OTRS ticket ID
- `ticket.queue.name` — queue name used
- `ticket.external_refs` — references to OTRS/Znuny

These are included in the `ActionResult.detail` string for observability.

---

## 4. Queue Routing Logic

The queue resolution follows a 3-tier fallback:

### Tier 1 — Category Match (Primary)

```python
queue_name = self.QUEUE_MAP.get(ctx.final_category)
```

If `ctx.final_category` exists in `QUEUE_MAP`, use that queue directly. This covers the three business categories:
- `"cliente"` → `"Support"`
- `"lead"` → `"Ventas"`
- `"proveedor"` → `"Proveedores"`

### Tier 2 — Department Match (Fallback)

If the category is not in `QUEUE_MAP` (e.g. a new category added later), fall back to routing departments:

```python
DEPARTMENT_QUEUE_MAP: dict[str, str] = {
    Department.SOPORTE.value: "Support",
    Department.COMERCIAL.value: "Ventas",
    Department.CONTABILIDAD.value: "Contabilidad",
    Department.PROVEEDORES.value: "Proveedores",
    Department.DIRECCION.value: "Direccion",
    Department.OTRO.value: "Support",
}
```

Iterate over `ctx.routing.departments` and use the first match. If multiple departments match, the first one wins.

### Tier 3 — Default Queue (Final Fallback)

If neither category nor departments match:

```python
queue_name = OtrsZnunySettings().default_queue  # "Support"
```

### Pseudocode

```python
def _resolve_queue(self, ctx: EmailContext) -> Queue:
    # Tier 1: category
    if ctx.final_category:
        mapped = self.QUEUE_MAP.get(ctx.final_category)
        if mapped:
            return Queue(name=mapped)
    
    # Tier 2: routing departments
    if ctx.routing and ctx.routing.departments:
        for dept in ctx.routing.departments:
            mapped = self.DEPARTMENT_QUEUE_MAP.get(dept)
            if mapped:
                return Queue(name=mapped)
    
    # Tier 3: default
    return Queue(name=OtrsZnunySettings().default_queue)
```

**Note**: `Queue` is a Pydantic model from `src.domain.ticketing` with just `name` required. This is passed directly to `TicketIngestionInput.queue`.

---

## 5. Integration Points

### 5.1 Where in `execute_all()`

The call is added at the end of `execute_all()`, after `_process_invoices()`:

```python
# In ActionExecutor.execute_all(), after line ~105 (invoice_action):
# 6. Crear ticket en OTRS (si está configurado)
ticket_action = await self._create_ticket(ctx)
actions.append(ticket_action)
```

### 5.2 How to Get OtrsZnunyClient / TicketIngestionService

The method instantiates `TicketIngestionService()` with default args — which internally creates an `OtrsZnunyClient` with default settings from env vars:

```python
from src.services.ticket_ingestion import TicketIngestionService

service = TicketIngestionService()
ticket = await service.ingest_email(input)
await service.aclose()
```

No DI or constructor injection is needed because:
- `OtrsZnunySettings` reads from env vars through Pydantic `BaseSettings`
- `OtrsZnunyClient` picks up settings automatically
- The `TicketIngestionService` factory creates all dependencies (see `src/services/ticket_ingestion.py` lines 29–36)

For testability, the method could accept an optional `service` parameter, but the simpler approach (following the existing pattern in `_sync_to_crm`) is to create the instance inline and mock at the module level in tests.

### 5.3 How to Store Result in `ctx.actions`

The `ActionResult` is appended to the local `actions` list inside `execute_all()`, which is later assigned to `ctx.actions`:

```python
ctx.actions = actions  # line ~107
```

The action name is `"otrs_ticket_create"`.

---

## 6. Testing Strategy

### 6.1 Test File

New tests added to a file or section at:
`backend/tests/test_action_executor.py`

Following the existing test patterns (see `test_ticket_ingestion.py`), we use a fake connector to avoid real HTTP calls.

### 6.2 Test Doubles

Reuse the existing `FakeOtrsConnector` (from `test_ticket_ingestion.py`), adapted to work with `TicketIngestionService`:

```python
fake_connector = FakeOtrsConnector()
service = TicketIngestionService(client=fake_connector)
```

For `ActionExecutor` tests specifically, the cleanest approach is to either:
1. **Monkey-patch `TicketIngestionService`** at the module level (similar to how `_sync_to_crm` imports `VTigerClient` inline)
2. **Inject the service** into `_create_ticket()` via an optional parameter

Option 1 is preferred because it follows the existing code pattern (see `_sync_to_crm` which imports `VTigerClient` inside the method body for testability).

### 6.3 Test Cases

| # | Test | Scenario | Expected |
|---|------|----------|----------|
| 1 | `test_create_ticket_maps_subject_body_sender` | Email with all fields, category=cliente | `ActionResult.success=True`, detail contains ticket ID |
| 2 | `test_create_ticket_maps_priority_from_urgency` | urgency=alta → HIGH, media → NORMAL, baja → LOW | Each combination produces correct `TicketPriority` |
| 3 | `test_create_ticket_maps_queue_from_category` | cliente→Support, lead→Ventas, proveedor→Proveedores | Each combination produces correct queue name |
| 4 | `test_create_ticket_falls_back_to_department_queue` | Unknown category + routing.departments=[soporte] | Queue = Support |
| 5 | `test_create_ticket_falls_back_to_default_queue` | Unknown category + no routing | Queue = Support (default) |
| 6 | `test_create_ticket_skips_when_otrs_not_configured` | OtrsZnunySettings with empty base_url | `ActionResult.success=True`, detail="OTRS no configurado" |
| 7 | `test_create_ticket_skips_when_category_is_nulo` | final_category=nulo | `ActionResult.success=True`, detail="Email nulo" |
| 8 | `test_create_ticket_handles_otrs_api_error` | OTRS returns 500 or timeout | `ActionResult.success=False`, pipeline continues |
| 9 | `test_create_ticket_includes_summary_as_comment` | extracted.summary present | comment is added as internal article |
| 10 | `test_execute_all_includes_ticket_action` | Full pipeline run | `ctx.actions` includes `otrs_ticket_create` |

### 6.4 Existing Test Protection

All existing tests in `test_ticket_ingestion.py` and `test_otrs_znuny.py` must continue to pass unchanged. The new tests are entirely additive.

### 6.5 Mock Strategy for `ActionExecutor` Tests

```python
@pytest.fixture(autouse=True)
def _patch_otrs_settings(monkeypatch):
    """Ensure OTRS is 'configured' during tests that need it."""
    monkeypatch.setattr(
        "src.integrations.otrs_znuny.settings.OtrsZnunySettings.is_configured",
        True,
    )

@pytest.fixture
def mock_ticket_service(monkeypatch):
    """Replace TicketIngestionService with fake connector."""
    fake = FakeOtrsConnector()
    
    async def fake_ingest(inbound):
        ticket = await fake.create_ticket(...)
        return ticket
    
    monkeypatch.setattr(
        "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
        fake_ingest,
    )
    return fake
```

---

## 7. Configuration

### 7.1 Class Constants on `ActionExecutor`

The mapping tables live as class-level constants for now:

| Constant | Type | Purpose |
|---|---|---|
| `QUEUE_MAP` | `dict[str, str]` | Category → OTRS queue name |
| `DEPARTMENT_QUEUE_MAP` | `dict[str, str]` | Routing department → OTRS queue name |
| `URGENCY_PRIORITY_MAP` | `dict[str, TicketPriority]` | Urgency string → TicketPriority enum |

**Rationale**: These are business-logic mappings that change infrequently. If the need for runtime configuration arises, they can be promoted to `Settings` (config.py) as env-driven dicts without changing the code structure — only the source of truth changes.

### 7.2 Guard Configuration

The guard uses `OtrsZnunySettings.is_configured` (computed property: `bool(self.base_url and self.api_token)`). This means:
- If `OTRS_ZNUNY_BASE_URL` and `OTRS_ZNUNY_API_TOKEN` are set → OTRS integration is active
- If either is empty → `is_configured` returns `False`, and the step skips with success

No additional env vars needed for this change.

### 7.3 Default Queue

`OtrsZnunySettings.default_queue` = `"Support"` (configurable via `OTRS_ZNUNY_DEFAULT_QUEUE` env var).

---

## 8. Affected Files

| File | Change | Impact |
|---|---|---|
| `backend/src/agents/action_executor.py` | Add `_create_ticket()` + call in `execute_all()` + class constants | ~40 lines new code |
| `backend/tests/test_action_executor.py` | New test file | ~200 lines new tests |

No existing files are modified beyond `action_executor.py`. No new dependencies are introduced.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| OTRS unavailable / timeout | Medium | `try/except` + `log.warning` + `ActionResult(success=False)` — pipeline continues |
| Queue name mismatch with OTRS | Low | QUEUE_MAP is explicit and test-covered; OTRS returns 400 if queue doesn't exist |
| Pipeline latency increase | Low | OTRS call is async with 15s default timeout; placed last so local effects are committed first |
| Recursion or double-creation | Low | No duplicate detection (out of scope) — IN-05 will handle this |

---

## 10. Open Questions

None. This change connects two existing, tested components with well-defined contracts.

---

## 11. Verification

- [ ] All mapping combinations (3 categories × 3 urgencies) produce correct TicketIngestionInput
- [ ] Nulo emails skip cleanly without calling OTRS
- [ ] Unconfigured OTRS skips cleanly without error
- [ ] OTRS API failure produces `ActionResult(success=False)` without breaking the pipeline
- [ ] All existing tests in `test_ticket_ingestion.py` and `test_otrs_znuny.py` pass
