"""Tests for ActionExecutor ticket creation functionality (IN-01).

Covers:
- T2.1: Queue/priority mapping constants and _resolve_queue logic
- T2.2: _create_ticket success path and field mapping
- T2.3: Graceful error handling (not configured, nulo, API failure)
"""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.action_executor import ActionExecutor
from src.domain.ticketing import (
    Queue,
    Ticket,
    TicketPriority,
    TicketState,
)
from src.orchestrator.context import (
    ActionResult,
    Category,
    Department,
    EmailContext,
    EmailData,
    ExtractedInfo,
    RoutingDecision,
    Urgency,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_otrs_settings(monkeypatch):
    """Ensure OTRS is 'configured' during tests (override per test if needed)."""
    monkeypatch.setattr(
        "src.integrations.otrs_znuny.settings.OtrsZnunySettings.is_configured",
        True,
    )


@pytest.fixture
def mock_db():
    """Create a mock async session for ActionExecutor."""
    return AsyncMock()


@pytest.fixture
def executor(mock_db):
    """Create an ActionExecutor with a mock DB session."""
    return ActionExecutor(db=mock_db)


@pytest.fixture
def sample_context():
    """Build a minimal EmailContext for testing ticket creation."""
    raw = EmailData(
        message_id="msg-123",
        subject="Problema con el servicio",
        body_plain="No puedo acceder al sistema",
        body_html="<p>No puedo acceder al sistema</p>",
        sender_name="Juan Pérez",
        sender_email="juan@example.com",
        recipients=["soporte@miempresa.com"],
        has_attachments=False,
        received_at=datetime(2026, 6, 17, 10, 0, tzinfo=timezone.utc),
    )
    extracted = ExtractedInfo(
        urgency="alta",
        action_required="soporte",
        summary="El usuario reporta problemas de acceso al sistema.",
        company="Ejemplo SA",
    )
    routing = RoutingDecision(
        departments=["soporte"],
        persons=[],
        rationale="Problema técnico",
    )
    return EmailContext(
        raw=raw,
        extracted=extracted,
        final_category=Category.CLIENTE.value,
        final_confidence=0.95,
        resolution_method="consensus",
        routing=routing,
    )


# ---------------------------------------------------------------------------
# T2.1 — Mapping constants and _resolve_queue
# ---------------------------------------------------------------------------


class TestQueuePriorityMapping:
    """T2.1: Validate QUEUE_MAP, DEPARTMENT_QUEUE_MAP, URGENCY_PRIORITY_MAP,
    and _resolve_queue 3-tier fallback."""

    def test_queue_map_has_correct_entries(self, executor):
        """QUEUE_MAP has exactly 3 business categories mapped correctly."""
        assert executor.QUEUE_MAP == {
            Category.CLIENTE.value: "Support",
            Category.LEAD.value: "Ventas",
            Category.PROVEEDOR.value: "Proveedores",
        }

    def test_department_queue_map_has_correct_entries(self, executor):
        """DEPARTMENT_QUEUE_MAP has all 6 departments mapped correctly."""
        assert executor.DEPARTMENT_QUEUE_MAP == {
            Department.SOPORTE.value: "Support",
            Department.COMERCIAL.value: "Ventas",
            Department.CONTABILIDAD.value: "Contabilidad",
            Department.PROVEEDORES.value: "Proveedores",
            Department.DIRECCION.value: "Direccion",
            Department.OTRO.value: "Support",
        }

    def test_urgency_priority_map_has_correct_entries(self, executor):
        """URGENCY_PRIORITY_MAP has all 3 urgencies mapped correctly."""
        assert executor.URGENCY_PRIORITY_MAP == {
            Urgency.ALTA.value: TicketPriority.HIGH,
            Urgency.MEDIA.value: TicketPriority.NORMAL,
            Urgency.BAJA.value: TicketPriority.LOW,
        }

    @pytest.mark.parametrize(
        "category,expected_queue",
        [
            (Category.CLIENTE.value, "Support"),
            (Category.LEAD.value, "Ventas"),
            (Category.PROVEEDOR.value, "Proveedores"),
        ],
    )
    def test_resolve_queue_maps_known_categories(
        self, executor, sample_context, category, expected_queue
    ):
        """Tier 1: Known categories map to correct queues via QUEUE_MAP."""
        ctx = sample_context
        ctx.final_category = category
        queue = executor._resolve_queue(ctx)
        assert queue.name == expected_queue

    def test_resolve_queue_falls_back_to_department(self, executor, sample_context):
        """Tier 2: Unknown category falls back to routing departments."""
        ctx = sample_context
        ctx.final_category = "unknown_category"
        ctx.routing.departments = [Department.SOPORTE.value]
        queue = executor._resolve_queue(ctx)
        assert queue.name == "Support"

    def test_resolve_queue_falls_back_to_default(self, executor, sample_context):
        """Tier 3: Unknown category + no routing falls back to default queue."""
        ctx = sample_context
        ctx.final_category = "unknown_category"
        ctx.routing = None
        queue = executor._resolve_queue(ctx)
        assert queue.name == "Support"

    @pytest.mark.parametrize(
        "urgency,expected_priority",
        [
            (Urgency.ALTA.value, TicketPriority.HIGH),
            (Urgency.MEDIA.value, TicketPriority.NORMAL),
            (Urgency.BAJA.value, TicketPriority.LOW),
        ],
    )
    def test_priority_maps_from_urgency(
        self, executor, sample_context, urgency, expected_priority
    ):
        """Urgency maps to correct TicketPriority via URGENCY_PRIORITY_MAP."""
        ctx = sample_context
        ctx.extracted.urgency = urgency
        inp = executor._build_ticket_input(ctx)
        assert inp.priority == expected_priority

    def test_priority_defaults_to_normal_when_urgency_missing(
        self, executor, sample_context
    ):
        """Missing urgency defaults to TicketPriority.NORMAL."""
        ctx = sample_context
        ctx.extracted = ExtractedInfo()  # urgency defaults to "media"
        inp = executor._build_ticket_input(ctx)
        assert inp.priority == TicketPriority.NORMAL

    def test_priority_defaults_to_normal_when_urgency_unknown(
        self, executor, sample_context
    ):
        """Unknown urgency value defaults toTicketPriority.NORMAL."""
        ctx = sample_context
        ctx.extracted.urgency = "superurgente"
        inp = executor._build_ticket_input(ctx)
        assert inp.priority == TicketPriority.NORMAL


# ---------------------------------------------------------------------------
# T2.2 — _build_ticket_input and _create_ticket success path
# ---------------------------------------------------------------------------


class TestBuildTicketInput:
    """T1.2 / T2.2: Validate _build_ticket_input field mapping."""

    def test_passes_subject_body_sender(self, executor, sample_context):
        """Subject, body, sender fields pass through correctly."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.subject == "Problema con el servicio"
        assert inp.body_text == "No puedo acceder al sistema"
        assert inp.body_html == "<p>No puedo acceder al sistema</p>"
        assert inp.sender_name == "Juan Pérez"
        assert inp.sender_email == "juan@example.com"

    def test_sets_queue_from_category(self, executor, sample_context):
        """Queue is resolved from category (cliente -> Support)."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.queue is not None
        assert inp.queue.name == "Support"

    def test_sets_priority_from_urgency(self, executor, sample_context):
        """Priority maps from alta urgency -> HIGH."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.priority == TicketPriority.HIGH

    def test_sets_state_new(self, executor, sample_context):
        """State is always TicketState.NEW."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.state == TicketState.NEW

    def test_includes_summary_as_comment(self, executor, sample_context):
        """Comment text comes from extracted.summary, not visible to customer."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.comment_text == "El usuario reporta problemas de acceso al sistema."
        assert inp.comment_visible_to_customer is False

    def test_includes_classification_metadata(self, executor, sample_context):
        """Metadata contains all 5 classification fields."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.metadata["category"] == "cliente"
        assert inp.metadata["confidence"] == 0.95
        assert inp.metadata["resolution_method"] == "consensus"
        assert inp.metadata["urgency"] == "alta"
        assert inp.metadata["action_required"] == "soporte"

    def test_passes_recipients_message_id_received_at(self, executor, sample_context):
        """Lists and optional fields pass through correctly."""
        inp = executor._build_ticket_input(sample_context)
        assert inp.recipients == ["soporte@miempresa.com"]
        assert inp.message_id == "msg-123"
        assert inp.received_at is not None

    def test_handles_none_extracted(self, executor, sample_context):
        """Graceful when ctx.extracted is None -> uses defaults."""
        ctx = sample_context
        ctx.extracted = None
        inp = executor._build_ticket_input(ctx)
        assert inp.priority == TicketPriority.NORMAL
        assert inp.comment_text is None
        assert inp.metadata["urgency"] == "media"
        assert inp.metadata["action_required"] is None

    def test_handles_empty_subject_body(self, executor, sample_context):
        """None subject and body default to empty strings."""
        ctx = sample_context
        ctx.raw.subject = None
        ctx.raw.body_plain = None
        inp = executor._build_ticket_input(ctx)
        assert inp.subject == ""
        assert inp.body_text == ""


class TestCreateTicketSuccess:
    """T1.3 / T2.2: _create_ticket success path."""

    @pytest.fixture(autouse=True)
    def _patch_ticket_service(self, monkeypatch):
        """Mock TicketIngestionService to avoid real HTTP calls."""

        async def fake_ingest(self, input_data):
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=input_data.queue or Queue(name="Support"),
                state=input_data.state,
                priority=input_data.priority,
            )

        async def fake_aclose(self_):
            pass

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest,
        )
        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.aclose",
            fake_aclose,
        )

    async def test_returns_action_result_with_success(self, executor, sample_context):
        """Successful ticket creation returns ActionResult(success=True)."""
        result = await executor._create_ticket(sample_context)
        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "TCK-999" in result.detail

    async def test_detail_contains_queue_name(self, executor, sample_context):
        """Detail string includes the queue name."""
        result = await executor._create_ticket(sample_context)
        assert "Support" in result.detail

    async def test_passes_summary_as_comment(self, executor, sample_context, monkeypatch):
        """Summary is forwarded as comment_text in ingestion input."""
        captured = []

        async def fake_ingest_capture(self, input_data):
            captured.append(input_data)
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=input_data.queue or Queue(name="Support"),
                state=input_data.state,
                priority=input_data.priority,
            )

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest_capture,
        )

        await executor._create_ticket(sample_context)
        assert len(captured) == 1
        assert captured[0].comment_text == "El usuario reporta problemas de acceso al sistema."
        assert captured[0].comment_visible_to_customer is False

    async def test_execute_all_includes_ticket_action(self, executor, sample_context, monkeypatch):
        """Full execute_all() produces 6 actions including otrs_ticket_create.

        Mocks all pipeline steps that touch external services or DB.
        """
        # Mock all pipeline methods that would cause side effects
        async def fake_save(ctx):
            return ActionResult(action="db_save", success=True, detail="Fake save")

        async def fake_crm(ctx):
            return ActionResult(action="crm_sync", success=True, detail="Fake CRM")

        async def fake_whatsapp(ctx):
            return ActionResult(action="whatsapp_alert", success=True, detail="Fake WhatsApp")

        async def fake_forward(ctx):
            return ActionResult(action="email_forward", success=True, detail="Fake forward")

        async def fake_invoice(ctx):
            return ActionResult(
                action="invoice_process", success=True, detail="Fake invoice"
            )

        monkeypatch.setattr(executor, "_save_to_db", fake_save)
        monkeypatch.setattr(executor, "_sync_to_crm", fake_crm)
        monkeypatch.setattr(executor, "_notify_whatsapp", fake_whatsapp)
        monkeypatch.setattr(executor, "_forward_email", fake_forward)
        monkeypatch.setattr(executor, "_process_invoices", fake_invoice)

        actions = await executor.execute_all(sample_context)

        assert len(actions) == 6
        assert actions[5].action == "otrs_ticket_create"
        assert actions[5].success is True


# ---------------------------------------------------------------------------
# T2.3 — Graceful handling: not configured, nulo, API error
# ---------------------------------------------------------------------------


class TestCreateTicketGracefulHandling:
    """T2.3: Verify pipeline handles error/edge cases gracefully."""

    @pytest.fixture(autouse=True)
    def _patch_ticket_service(self, monkeypatch):
        """Default mock for ingest_email (overridden per test)."""

        async def fake_ingest(self, input_data):
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=input_data.queue or Queue(name="Support"),
                state=input_data.state,
                priority=input_data.priority,
            )

        async def fake_aclose(self_):
            pass

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest,
        )
        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.aclose",
            fake_aclose,
        )

    async def test_skips_when_otrs_not_configured(
        self, executor, sample_context, monkeypatch
    ):
        """OTRS not configured -> ActionResult(success=True) with skip detail.

        Also verifies NO call to ingest_email (mock spy).
        """
        call_count = 0

        async def fake_ingest_spy(self, input_data):
            nonlocal call_count
            call_count += 1
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=Queue(name="Support"),
                state=TicketState.NEW,
                priority=TicketPriority.NORMAL,
            )

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest_spy,
        )
        monkeypatch.setattr(
            "src.integrations.otrs_znuny.settings.OtrsZnunySettings.is_configured",
            False,
        )

        result = await executor._create_ticket(sample_context)

        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "OTRS no configurado" in result.detail
        assert call_count == 0  # No API call made

    async def test_skips_when_category_is_nulo(self, executor, sample_context, monkeypatch):
        """Nulo category -> ActionResult(success=True) with skip detail.

        Also verifies NO call to ingest_email.
        """
        call_count = 0

        async def fake_ingest_spy(self, input_data):
            nonlocal call_count
            call_count += 1
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=Queue(name="Support"),
                state=TicketState.NEW,
                priority=TicketPriority.NORMAL,
            )

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest_spy,
        )

        ctx = sample_context
        ctx.final_category = "nulo"
        result = await executor._create_ticket(ctx)

        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "Email nulo" in result.detail
        assert call_count == 0  # No API call made

    async def test_handles_none_category_as_nulo(self, executor, sample_context, monkeypatch):
        """None category is treated like nulo and skipped."""
        call_count = 0

        async def fake_ingest_spy(self, input_data):
            nonlocal call_count
            call_count += 1
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=Queue(name="Support"),
                state=TicketState.NEW,
                priority=TicketPriority.NORMAL,
            )

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest_spy,
        )

        ctx = sample_context
        ctx.final_category = None
        result = await executor._create_ticket(ctx)

        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "Email nulo" in result.detail
        assert call_count == 0

    async def test_handles_otrs_api_error(
        self, executor, sample_context, monkeypatch, caplog
    ):
        """OTRS API error -> ActionResult(success=False), warning logged."""
        import logging

        async def fake_ingest_error(self, input_data):
            raise RuntimeError("Connection timeout")

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest_error,
        )

        with caplog.at_level(logging.WARNING):
            result = await executor._create_ticket(sample_context)

        assert result.action == "otrs_ticket_create"
        assert result.success is False
        assert "Connection timeout" in result.detail
        # Check warning was logged
        warning_messages = [
            rec.message for rec in caplog.records if rec.levelno == logging.WARNING
        ]
        assert any("Error creando ticket OTRS" in msg for msg in warning_messages)


# ---------------------------------------------------------------------------
# IN-05 — Dedup: Pre-check + post-save + message_id propagation
# ---------------------------------------------------------------------------


class TestCreateTicketDedup:
    """IN-05: Dedup scenarios for _create_ticket() and _save_email().

    Covers:
    - T1.3: message_id propagation in _save_email()
    - T1.4: Pre-check skip when otrs_ticket_id already exists
    - T1.5: Post-save otrs_ticket_id set after ticket creation
    - Fail-open: DB error in pre-check does not block ticket creation
    - Fail-soft: DB error in post-save does not affect ActionResult
    """

    @pytest.fixture(autouse=True)
    def _patch_ticket_service(self, monkeypatch):
        """Mock TicketIngestionService to avoid real HTTP calls.
        Uses a call counter spy for verifying ingest_email calls."""

        call_counter: list[int] = [0]

        async def fake_ingest(self, input_data):
            call_counter[0] += 1
            return Ticket(
                id="TCK-999",
                subject=input_data.subject,
                queue=input_data.queue or Queue(name="Support"),
                state=input_data.state,
                priority=input_data.priority,
            )

        async def fake_aclose(self_):
            pass

        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.ingest_email",
            fake_ingest,
        )
        monkeypatch.setattr(
            "src.services.ticket_ingestion.TicketIngestionService.aclose",
            fake_aclose,
        )

        return call_counter

    # ── Scenario 1: Skip when ticket already exists (T1.4) ────────────────

    async def test_skips_when_ticket_already_exists(
        self, executor, sample_context, _patch_ticket_service
    ):
        """Pre-check finds existing otrs_ticket_id → skip with early return."""
        call_counter = _patch_ticket_service

        email_mock = MagicMock()
        email_mock.message_id = "msg-123"
        email_mock.otrs_ticket_id = "TCK-1"
        email_mock.otrs_ticket_created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = email_mock
        executor.db.execute = AsyncMock(return_value=mock_result)

        result = await executor._create_ticket(sample_context)

        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "ya existe" in result.detail
        assert call_counter[0] == 0  # ingest_email was NOT called

    # ── Scenario 2: Create when no otrs_ticket_id (T1.4 + T1.5) ───────────

    async def test_creates_ticket_when_no_otrs_ticket_id(
        self, executor, sample_context, _patch_ticket_service
    ):
        """No otrs_ticket_id → pre-check continues, post-save sets the ID."""
        call_counter = _patch_ticket_service

        email_mock = MagicMock()
        email_mock.message_id = "msg-123"
        email_mock.otrs_ticket_id = None
        email_mock.otrs_ticket_created_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = email_mock
        executor.db.execute = AsyncMock(return_value=mock_result)
        executor.db.commit = AsyncMock()

        result = await executor._create_ticket(sample_context)

        assert result.action == "otrs_ticket_create"
        assert result.success is True
        assert "TCK-999" in result.detail
        assert call_counter[0] == 1  # ingest_email WAS called once
        # Post-save should have set otrs_ticket_id on the email mock
        assert email_mock.otrs_ticket_id == "TCK-999"
        assert email_mock.otrs_ticket_created_at is not None
        # commit was called (once for post-save)
        executor.db.commit.assert_awaited_once()

    # ── Scenario 3: Missing message_id (T1.4) ─────────────────────────────

    async def test_missing_message_id_skips_pre_check(
        self, executor, sample_context, _patch_ticket_service
    ):
        """message_id=None → pre-check AND post-save are skipped."""
        call_counter = _patch_ticket_service

        ctx = sample_context
        ctx.raw.message_id = None

        # db.execute should never be called — raise if it is
        executor.db.execute = AsyncMock(
            side_effect=RuntimeError("No db.execute should happen")
        )

        result = await executor._create_ticket(ctx)

        assert result.success is True
        assert call_counter[0] == 1  # Ticket created normally

    # ── Scenario 4: DB error in pre-check — fail-open (T1.4) ──────────────

    async def test_db_error_in_pre_check_fails_open(
        self, executor, sample_context, _patch_ticket_service, caplog
    ):
        """Pre-check raises → warning logged, ticket creation continues."""
        call_counter = _patch_ticket_service

        executor.db.execute = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        with caplog.at_level(logging.WARNING):
            result = await executor._create_ticket(sample_context)

        assert result.success is True
        assert call_counter[0] == 1  # Ticket created despite pre-check error
        # Verify fail-open warning
        warning_messages = [
            rec.message for rec in caplog.records if rec.levelno == logging.WARNING
        ]
        assert any("fail-open" in msg for msg in warning_messages)

    # ── Scenario 5: DB error in post-save — fail-soft (T1.5) ──────────────

    async def test_db_error_in_post_save_fails_soft(
        self, executor, sample_context, _patch_ticket_service, caplog
    ):
        """Post-save commit fails → warning logged, ActionResult still success."""
        call_counter = _patch_ticket_service

        email_mock = MagicMock()
        email_mock.message_id = "msg-123"
        email_mock.otrs_ticket_id = None
        email_mock.otrs_ticket_created_at = None

        # Pre-check succeeds (returns email without ticket)
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = email_mock

        # Post-save also needs a db.execute — return email again
        executor.db.execute = AsyncMock(return_value=first_result)

        # But commit raises on post-save
        executor.db.commit = AsyncMock(side_effect=RuntimeError("Commit failed"))

        with caplog.at_level(logging.WARNING):
            result = await executor._create_ticket(sample_context)

        assert result.success is True
        assert "TCK-999" in result.detail
        assert call_counter[0] == 1  # Ticket was created
        # Verify fail-soft warning
        warning_messages = [
            rec.message for rec in caplog.records if rec.levelno == logging.WARNING
        ]
        assert any("No se pudo persistir" in msg for msg in warning_messages)
        # rollback was called
        executor.db.rollback.assert_awaited_once()

    # ── Scenario 6: Auto-generated message_id propagates (T1.3) ───────────

    async def test_message_id_propagates_to_context(
        self, executor, sample_context, monkeypatch
    ):
        """_save_email() sets ctx.raw.message_id when auto-generated."""
        ctx = sample_context

        # Mock contact
        contact = MagicMock()
        contact.id = "contact-id"
        contact.name = "Test"
        contact.email = "test@example.com"

        # Mock _get_or_create_account_id
        async def fake_get_account(_ctx):
            return "account-id"

        monkeypatch.setattr(executor, "_get_or_create_account_id", fake_get_account)

        # Mock db.execute for duplicate check to return None (no duplicate)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        executor.db.execute = AsyncMock(return_value=mock_result)

        # Set message_id to None — should be auto-generated
        ctx.raw.message_id = None

        await executor._save_email(ctx, contact)

        assert ctx.raw.message_id is not None
        assert ctx.raw.message_id.startswith("auto-")

