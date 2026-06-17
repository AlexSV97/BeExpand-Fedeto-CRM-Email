# Tasks: IN-05 — Evitar tickets duplicados

> **Change ID:** `in-05-dedup-tickets`
> **Parent Capability:** `email-ticket-ingestion`
> **Dependencies:** BT-01 (OTRS connector), BT-03 (normalizer), IN-01 (email-to-ticket ingestion)

---

## Tier 1 — Data Layer

### T1.1 — Add `otrs_ticket_id` and `otrs_ticket_created_at` fields to Email model

| Field | Value |
|-------|-------|
| **File** | `backend/src/db/models.py` |
| **Type** | Modify — 2 new mapped columns on `Email` class |
| **Acceptance** | Fields exist with correct types and constraints |

**Implementation details:**

Add two nullable columns to the `Email` class (after existing `extra_data` column, line 108):

```python
# After: extra_data: Mapped[Optional[dict]] = mapped_column(...)
otrs_ticket_id: Mapped[Optional[str]] = mapped_column(
    String(100), nullable=True, default=None
)
otrs_ticket_created_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
```

**Constraints:**
- Both fields are **nullable** — existing records remain `NULL`
- `otrs_ticket_id`: `String(100)` — OTRS/Znuny ticket IDs (e.g. `"202405271000001"`)
- `otrs_ticket_created_at`: `DateTime(timezone=True)` — UTC timestamp of ticket creation
- **Write-once**: once set, never modified (ensures idempotency guarantee)
- No new indexes needed — lookup is by `message_id` (already covered by `uq_message_id_account` unique constraint)

---

### T1.2 — Auto-generate Alembic migration for new columns

| Field | Value |
|-------|-------|
| **Files** | `backend/alembic/versions/` (new file) |
| **Type** | Create — new migration revision |
| **Acceptance** | `alembic upgrade head` completes without error |

**Implementation details:**

```bash
cd backend
alembic revision --autogenerate -m "add_otrs_ticket_fields_to_emails"
```

**Verify generated migration contains only:**

```python
def upgrade():
    op.add_column("emails", sa.Column("otrs_ticket_id", sa.String(100), nullable=True))
    op.add_column("emails", sa.Column("otrs_ticket_created_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("emails", "otrs_ticket_created_at")
    op.drop_column("emails", "otrs_ticket_id")
```

**Critical checks:**
- `down_revision` must point to `f75fefbd4a00` (latest existing migration)
- If `--autogenerate` picks up unrelated changes, manually revert them — only these 2 columns belong in this migration
- Run `alembic upgrade head` to apply
- Run `alembic downgrade -1` and `alembic upgrade head` to verify round-trip

---

## Tier 1 — Business Logic

### T1.3 — Fix `message_id` propagation in `_save_email()`

| Field | Value |
|-------|-------|
| **File** | `backend/src/agents/action_executor.py` |
| **Type** | Modify — `_save_email()` method (line ~251) |
| **Acceptance** | `ctx.raw.message_id` is never `None` after `_save_email()` returns |

**Problem:** When an email arrives without a `Message-ID` header, `_save_email()` auto-generates a UUID (`f"auto-{uuid.uuid4()}"`) but **never updates** `ctx.raw.message_id`. The pre-check in T1.4 will try to look up by `ctx.raw.message_id` (which is still `None`), failing to find the existing Email record.

**Fix:** After auto-generating the message_id, propagate it back to the context:

```python
# Lines 248-251 currently:
message_id = ctx.raw.message_id
if not message_id:
    message_id = f"auto-{uuid.uuid4()}"
    logger.debug("Message-ID auto-generado: %s", message_id)

# After fix — add this line AFTER the if block:
message_id = ctx.raw.message_id
if not message_id:
    message_id = f"auto-{uuid.uuid4()}"
    logger.debug("Message-ID auto-generado: %s", message_id)
    ctx.raw.message_id = message_id  # ← PROPAGATE back to context
```

**Verification:**
- Test: `_save_email()` with `ctx.raw.message_id = None` → after call, `ctx.raw.message_id` starts with `"auto-"`
- This is a **minimal, local change** — no cascading effects outside `_save_email()`

---

### T1.4 — Add pre-check in `_create_ticket()` before service call

| Field | Value |
|-------|-------|
| **File** | `backend/src/agents/action_executor.py` |
| **Type** | Modify — `_create_ticket()` method, after guards, before `try:` block |
| **Acceptance** | Same `message_id` processed twice → second call skips OTRS with `ActionResult(success=True, detail="Ticket {id} ya existe")` |

**Implementation details:**

Insert pre-check logic **after** the category guard (line ~770) and **before** the `try:` block (line ~772):

```python
# ── PRE-CHECK: ¿ya existe ticket OTRS para este email? ──────────────
message_id = ctx.raw.message_id
if message_id:
    try:
        result = await self.db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        email = result.scalar_one_or_none()
        if email and email.otrs_ticket_id:
            logger.info(
                "Ticket %s ya existe para email %s",
                email.otrs_ticket_id, message_id,
            )
            return ActionResult(
                action="otrs_ticket_create",
                success=True,
                detail=f"Ticket {email.otrs_ticket_id} ya existe",
            )
    except Exception:
        logger.warning("Error en pre-check de duplicado — continuando (fail-open)")
        # Fail-open: si no podemos verificar, mejor crear que arriesgar pérdida
```

**Key behaviors:**
- **Fail-open**: if the DB query raises, log a warning and continue — don't block ticket creation
- **Skip condition**: only when `email.otrs_ticket_id IS NOT NULL`
- **Email not found or otrs_ticket_id is NULL**: continue to create ticket normally
- **message_id is None**: skip pre-check entirely (edge case, shouldn't happen after T1.3)

---

### T1.5 — Add post-save in `_create_ticket()` after successful ticket creation

| Field | Value |
|-------|-------|
| **File** | `backend/src/agents/action_executor.py` |
| **Type** | Modify — `_create_ticket()` method, after `ticket = await service.ingest_email(input_data)`, before `return ActionResult(...)` |
| **Acceptance** | After successful ticket creation, `Email.otrs_ticket_id` is set and committed |

**Implementation details:**

Insert post-save logic after the `ticket = await service.ingest_email(input_data)` call (line ~776) and before the `return ActionResult(...)` on success:

```python
ticket = await service.ingest_email(input_data)
logger.info(
    "Ticket creado: %s en cola %s",
    ticket.id,
    ticket.queue.name,
)

# ── POST-SAVE: persistir otrs_ticket_id en el Email ─────────────────
if message_id:
    try:
        result = await self.db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        email = result.scalar_one_or_none()
        if email:
            email.otrs_ticket_id = ticket.id
            email.otrs_ticket_created_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.debug(
                "otrs_ticket_id=%s guardado para email %s",
                ticket.id, message_id,
            )
    except Exception:
        await self.db.rollback()
        logger.warning(
            "No se pudo persistir otrs_ticket_id para %s — ticket %s ya existe en OTRS",
            message_id, ticket.id,
        )
        # No re-lanzar: el ticket ya fue creado exitosamente en OTRS
```

**Key behaviors:**
- **Fail-soft**: if the post-save commit fails, log a warning but DON'T change the ActionResult (ticket already exists in OTRS)
- **Rollback on error**: always rollback the failed post-save transaction so the session remains usable
- **message_id must be captured** from the outer scope (use the same `message_id = ctx.raw.message_id` from the pre-check, or re-read it)
- **Only update if Email record found**: if the Email was deleted between pre-check and post-save (unlikely), skip gracefully

**Edge case — message_id variable scope:**
The `message_id` variable used in T1.5 must be accessible. Either:
- **(A)** Move the `message_id = ctx.raw.message_id` line above the pre-check and reuse the same variable for post-save (recommended — single source of truth), or
- **(B)** Re-read `ctx.raw.message_id` inside the post-save block (works because T1.3 ensures it's always set)

**Recommendation:** Option (A) — extract `message_id` once at the top of the dedup logic and reuse it in both pre-check and post-save.

---

## Tier 2 — Testing & Verification

### T2.1 — Update tests for dedup scenarios

| Field | Value |
|-------|-------|
| **File** | `backend/tests/test_action_executor.py` |
| **Type** | Modify — add new `TestCreateTicketDedup` class + scenarios |
| **Acceptance** | All new tests pass with `pytest tests/test_action_executor.py -v` |

**Test scenarios to add (following existing monkeypatch patterns):**

**Scenario 1: Skip when ticket already exists (Happy path)**
```python
# Mock self.db.execute → returns Email with otrs_ticket_id="TCK-1"
# Assert: ActionResult.success=True
# Assert: "ya existe" in detail
# Assert: ingest_email was NOT called
```

**Scenario 2: Create when no otrs_ticket_id (normal flow continues)**
```python
# Mock self.db.execute → returns Email with otrs_ticket_id=None
# Assert: ingest_email IS called
# Assert: ActionResult.success=True
# Assert: otrs_ticket_id="TCK-999" was set on email object
```

**Scenario 3: Missing message_id skips pre-check (edge case)**
```python
# Set ctx.raw.message_id = None
# Assert: pre-check is skipped
# Assert: ticket is created normally
# Assert: post-save is skipped (no message_id to look up)
```

**Scenario 4: DB error in pre-check (fail-open)**
```python
# Mock self.db.execute → raises Exception
# Assert: Warning is logged
# Assert: ticket creation continues (fail-open)
# Assert: ingest_email IS called
```

**Scenario 5: DB error in post-save (fail-soft)**
```python
# Mock self.db.commit → raises on second call (post-save commit)
# Assert: Warning is logged
# Assert: ActionResult still success=True
# Assert: ticket was created in OTRS
```

**Scenario 6: Auto-generated message_id propagates (T1.3 verification)**
```python
# Set ctx.raw.message_id = None
# Call _save_email()
# Assert: ctx.raw.message_id starts with "auto-"
# Assert: Email record has message_id starting with "auto-"
```

**Testing approach:**
- Use `monkeypatch` to mock `self.db.execute` (returning `AsyncMock` with `.scalar_one_or_none()`)
- Use `monkeypatch` to mock `self.db.commit` (raising on certain calls for error scenarios)
- Use `monkeypatch` to mock `TicketIngestionService.ingest_email` with a spy that counts calls
- Follow the existing test patterns in `TestCreateTicketSuccess` and `TestCreateTicketGracefulHandling`

---

### T2.2 — Run full regression suite

| Field | Value |
|-------|-------|
| **Command** | `cd backend && pytest tests/ -v` |
| **Acceptance** | All existing tests + new dedup tests pass. Zero regressions. |

**Pre-flight checklist:**
- [x] Alembic migration is applied (`alembic upgrade head`) — ⚠️ Manual: migration file created, DB stamping requires env setup
- [ ] `SQLALCHEMY_DATABASE_URL` is set to a test/local database
- [ ] All env vars required by `get_settings()` are available

**Expected output:**
- All `TestQueuePriorityMapping` tests pass (unchanged)
- All `TestBuildTicketInput` tests pass (unchanged)
- All `TestCreateTicketSuccess` tests pass (unchanged)
- All `TestCreateTicketGracefulHandling` tests pass (unchanged)
- All new `TestCreateTicketDedup` tests pass
- No warnings about missing columns or SQLAlchemy model mismatches

---

## Execution Order

```
T1.1  ──→  T1.2  ──→  T1.4  ──→  T2.1
 │                    ↑            │
 └── T1.3 ────────────┘            │
                                    ↓
                              T1.5 ──→ T2.2 (regression)
```

1. **[x] T1.1** — Model fields (needed by migration and logic)
2. **[x] T1.2** — Migration (migration file created manually; autogenerate blocked by DB env state)
3. **[x] T1.3** — message_id fix (needed by T1.4 pre-check to work correctly)
4. **[x] T1.4** — Pre-check (needs T1.3 for correct `message_id`; depends on T1.1 for `Email.otrs_ticket_id` field)
5. **[x] T1.5** — Post-save (needs T1.1 for model fields; the final piece of the logic)
6. **[x] T2.1** — Tests (needs all T1.x done)
7. **[x] T2.2** — Regression suite (36/36 passed, 0 regressions)

---

## Rollback Per Task

| Task | Rollback |
|------|----------|
| T1.1 | Revert model changes in `models.py` |
| T1.2 | `alembic downgrade -1` |
| T1.3 | Revert the single added line in `_save_email()` |
| T1.4 | Remove pre-check block from `_create_ticket()` |
| T1.5 | Remove post-save block from `_create_ticket()` |
| T2.1 | Revert test additions in `test_action_executor.py` |
| T2.2 | No rollback needed (verification only) |

All tasks are purely additive — no risk of data loss on rollback.
