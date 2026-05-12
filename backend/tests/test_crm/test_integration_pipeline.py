"""
Tests de integración: pipeline completo Email → ClassifierService → CrmSyncService → VTiger.

Flujo real:
  1. EmailParsed → ClassifierService.classify() → ClassificationResult + DB persist
  2. ClassificationResult → CrmSyncService.sync_contact() → VTiger API (HTTP mockeado)
  3. SyncLogEntry creado en DB real (SQLite en memoria)

VTiger HTTP se mockea con respx. La DB es SQLite en memoria real.
Los servicios usan sesiones SQLAlchemy reales, no mocks.

NOTA sobre mockeo de VTiger HTTP:
  respx no soporta data__contains para form-encoded POST bodies,
  por eso usamos side_effect handlers que inspeccionan el body/params.
"""

import pytest
import pytest_asyncio
import respx
from datetime import datetime, timezone
from httpx import Response, URL
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.db.models import (
    Account,
    ClassificationHistory,
    ClassificationRule,
    Email,
    SyncLogEntry,
    SyncStatus,
)
from src.db.session import Base
from src.crm.vtiger_client import VtigerClient
from src.crm.sync_service import CrmSyncService
from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.rule_engine import RuleEngineClassifier
from src.email_processor.classifier.service import ClassifierService

VTIGER_URL = "https://fake-vtiger.test"


# ── Helpers para mockear VTiger HTTP con respx ──
# respx no puede usar data__contains con form-encoded POST bodies,
# así que definimos handlers que inspeccionan el body crudo.


def _post_handler(routes: dict) -> callable:
    """Crea un handler side_effect para respx.post().

    Args:
        routes: dict de {identificador_en_body: Response}
                Ej: {"operation=login": Response(200, json=...),
                     "elementType=Contacts": Response(200, json=...)}

    El handler busca la primera key de routes que esté en el body.
    Si ninguna matchea, devuelve 500 por defecto.
    """
    async def handler(request):
        body = request.content.decode("utf-8", errors="replace")
        for pattern, response in routes.items():
            if pattern in body:
                return response
        return Response(500, json={"success": False, "error": {"message": f"Unmocked POST: {body[:100]}"}})
    return handler


def _get_handler(routes: dict) -> callable:
    """Crea un handler side_effect para respx.get().

    Args:
        routes: dict de {param_en_query_string: Response}
                Ej: {"operation=getchallenge": Response(200, json=...),
                     "operation=search": Response(200, json=...)}
    """
    async def handler(request):
        query = str(request.url.params)
        for pattern, response in routes.items():
            if pattern in query:
                return response
        return Response(500, json={"success": False, "error": {"message": f"Unmocked GET: {query}"}})
    return handler


# ── DB Fixtures ──


@pytest_asyncio.fixture
async def in_memory_session():
    """SQLite en memoria con todas las tablas creadas."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def account(in_memory_session):
    """Account mínimo para FK references."""
    acc = Account(
        id="acc-int-1",
        name="Integration Test",
        email_host="imap.test.com",
        email_port=993,
        email_user="test@test.com",
        email_pass="pass",
    )
    in_memory_session.add(acc)
    await in_memory_session.commit()
    return acc


@pytest_asyncio.fixture
async def email_record(in_memory_session, account):
    """Email en DB para clasificar y sincronizar."""
    email = Email(
        id="email-int-1",
        account_id=account.id,
        message_id="msg-int-001",
        subject="Cotización de materiales para construcción",
        body_plain="Necesito cotización de 500 bolsas de cemento y varilla.",
        sender_email="cliente@constructora.com",
        sender_name="Carlos Méndez",
        category="pendiente",
        received_at=datetime.now(timezone.utc),
    )
    in_memory_session.add(email)
    await in_memory_session.commit()
    return email


@pytest_asyncio.fixture
async def classification_rules(in_memory_session):
    """Reglas de clasificación seed para los tests de integración."""
    rules = [
        ClassificationRule(
            id="rule-int-lead",
            category="lead",
            keywords=["cotización", "presupuesto"],
            match_fields=["subject", "body_plain"],
            priority=10,
            confidence=0.85,
        ),
        ClassificationRule(
            id="rule-int-cliente",
            category="cliente",
            keywords=["factura", "pago"],
            match_fields=["subject"],
            priority=20,
            confidence=0.9,
        ),
    ]
    for r in rules:
        in_memory_session.add(r)
    await in_memory_session.commit()
    return rules


@pytest_asyncio.fixture
async def vtiger_client():
    """VtigerClient real — HTTP mockeado por respx en cada test.

    Importante: NO se hace login real. Cada test setea _session_id
    o mockea los endpoints según necesite.
    """
    client = VtigerClient(
        url=VTIGER_URL,
        username="admin@test.com",
        access_key="test-key",
    )
    yield client
    await client.close()


# ── Helpers ──


def make_email_parsed(email_record: Email) -> EmailParsed:
    """Construye un EmailParsed desde un Email DB record."""
    return EmailParsed(
        message_id=email_record.message_id or "",
        subject=email_record.subject or "",
        body_plain=email_record.body_plain or "",
        body_html=email_record.body_html or "",
        sender_email=email_record.sender_email,
        sender_name=email_record.sender_name or "",
        recipients=["comercial@beexpand.com"],
        date=email_record.received_at,
    )


# ══════════════════════════════════════════════════
# Tests de integración: Classify → Sync → Verify
# ══════════════════════════════════════════════════


class TestPipelineLead:
    """Pipeline completo con clasificación LEAD → crea contacto + oportunidad en VTiger."""

    @pytest.mark.asyncio
    async def test_lead_creates_contact_and_opportunity(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """Email clasificado como Lead:
        - ClassificationHistory guardado
        - Email.category actualizado
        - Contacto creado en VTiger
        - Oportunidad creada en VTiger
        - SyncLogEntry COMPLETED en DB
        """
        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)

        # Step 1: Classify
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)

        assert result.category == "lead"
        assert result.confidence == 0.85
        assert result.details["matched_rule_id"] == "rule-int-lead"

        stmt = select(ClassificationHistory).where(ClassificationHistory.email_id == email_record.id)
        hist = (await in_memory_session.execute(stmt)).scalar_one()
        assert hist.category == "lead"

        await in_memory_session.refresh(email_record)
        assert email_record.category == "lead"

        # Step 2: Sync with VTiger (HTTP mockeado)
        vtiger_client._session_id = "sess-int-123"

        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=search": Response(200, json={"success": True, "result": []}),
            })

            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "elementType=Contacts": Response(200, json={"success": True, "result": {"id": "12x100"}}),
                "elementType=Potentials": Response(200, json={"success": True, "result": {"id": "13x200"}}),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        # Step 3: Assert sync result
        assert sync_result["success"] is True
        assert sync_result["contact_id"] == "12x100"
        assert sync_result["opportunity_id"] == "13x200"
        assert sync_result["action"] == "created"

        # Step 4: Verify SyncLogEntry in DB
        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.COMPLETED
        assert log.details["contact_id"] == "12x100"
        assert log.details["opportunity_id"] == "13x200"
        assert log.details["action"] == "created"
        assert log.details["category"] == "lead"
        assert log.created_at is not None

    @pytest.mark.asyncio
    async def test_lead_updates_existing_contact(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """Lead con contacto ya existente en VTiger → actualiza, NO crea."""
        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)
        assert result.category == "lead"

        vtiger_client._session_id = "sess-int-456"

        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=search": Response(
                    200,
                    json={"success": True, "result": [{"id": "12x50", "email": "cliente@constructora.com"}]},
                ),
            })

            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "operation=update": Response(200, json={"success": True, "result": {"id": "12x50"}}),
                "elementType=Potentials": Response(200, json={"success": True, "result": {"id": "13x300"}}),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        assert sync_result["success"] is True
        assert sync_result["contact_id"] == "12x50"
        assert sync_result["opportunity_id"] == "13x300"
        assert sync_result["action"] == "updated"

        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.COMPLETED
        assert log.details["action"] == "updated"


class TestPipelineCliente:
    """Pipeline con clasificación CLIENTE → solo contacto, SIN oportunidad."""

    @pytest.mark.asyncio
    async def test_cliente_creates_contact_only(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """Cliente NO es Lead → solo crea contacto, sin oportunidad."""
        # Forzar clasificación como cliente: "factura" matchea la regla cliente,
        # no está en keywords de lead ("cotización", "presupuesto")
        email_record.subject = "Factura mensual de servicios"
        email_record.body_plain = "Adjuntamos la factura del mes de abril."
        in_memory_session.add(email_record)
        await in_memory_session.commit()

        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)

        assert result.category == "cliente"
        assert result.confidence == 0.9

        vtiger_client._session_id = "sess-int-789"

        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=search": Response(200, json={"success": True, "result": []}),
            })

            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "elementType=Contacts": Response(200, json={"success": True, "result": {"id": "12x700"}}),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        assert sync_result["success"] is True
        assert sync_result["contact_id"] == "12x700"
        assert sync_result["opportunity_id"] is None  # Cliente no genera oportunidad
        assert sync_result["action"] == "created"

        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.COMPLETED


class TestPipelineNulo:
    """Pipeline con clasificación NULO → sync skipped."""

    @pytest.mark.asyncio
    async def test_nulo_skips_sync_entirely(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """Categoría nulo → sync devuelve skipped, NO toca VTiger ni crea SyncLogEntry."""
        # Email que NO matchea ninguna regla
        email_record.subject = "Reunión de equipo para el jueves"
        email_record.body_plain = "Confirmar asistencia a la reunión semanal."
        in_memory_session.add(email_record)
        await in_memory_session.commit()

        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)

        assert result.category == "nulo"

        # Sync — SIN respx mock, si llegara a tocar VTiger rompería
        sync_result = await sync.sync_contact(
            email_data=email_parsed,
            classification=result,
            email_record_id=email_record.id,
        )

        assert sync_result["success"] is True
        assert sync_result["action"] == "skipped"
        assert sync_result["contact_id"] is None
        assert sync_result["opportunity_id"] is None

        # NO debe haber SyncLogEntry para emails nulos
        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        count = (await in_memory_session.execute(stmt)).scalars().all()
        assert len(count) == 0


class TestPipelineError:
    """Pipeline con errores de VTiger — el pipeline NO debe romperse."""

    @pytest.mark.asyncio
    async def test_vtiger_unavailable_does_not_break_pipeline(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """VTiger devuelve error 500 → sync falla, FAILED SyncLogEntry, email sigue clasificado."""
        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)
        assert result.category == "lead"
        await in_memory_session.refresh(email_record)
        assert email_record.category == "lead"

        vtiger_client._session_id = "sess-int-999"

        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=search": Response(500),
            })

            # Los POST que se disparen (create_contact, create_opportunity) también fallan
            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "elementType=Contacts": Response(500),
                "elementType=Potentials": Response(500),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        assert sync_result["success"] is False
        assert sync_result["action"] == "error"
        assert sync_result["contact_id"] is None
        assert sync_result["opportunity_id"] is None

        # SyncLogEntry FAILED
        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.FAILED
        assert "error" in log.details

        # Email sigue clasificado aunque VTiger haya fallado
        await in_memory_session.refresh(email_record)
        assert email_record.category == "lead"

    @pytest.mark.asyncio
    async def test_auth_error_still_keeps_email_classified(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """VTiger auth error → FAILED log, pero email sigue clasificado en DB."""
        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)
        assert result.category == "lead"

        # No setear _session_id → va a intentar login
        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=getchallenge": Response(200, json={"success": True, "result": {"token": "tok"}}),
            })

            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "operation=login": Response(200, json={"success": False, "error": {"message": "Invalid credentials"}}),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        assert sync_result["success"] is False
        assert sync_result["action"] == "error"

        # Email sigue clasificado
        await in_memory_session.refresh(email_record)
        assert email_record.category == "lead"

        # FAILED log
        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.FAILED


class TestPipelineAutoLogin:
    """Login automático cuando no hay sesión activa en VtigerClient."""

    @pytest.mark.asyncio
    async def test_auto_login_on_first_sync(
        self, in_memory_session, email_record, classification_rules, vtiger_client,
    ):
        """Sin session_id → CrmSyncService hace login automático y luego crea contacto+oportunidad."""
        engine = RuleEngineClassifier(session=in_memory_session, rules=classification_rules)
        classifier = ClassifierService(classifier=engine, session=in_memory_session)
        sync = CrmSyncService(vtiger_client=vtiger_client, db_session=in_memory_session)

        email_parsed = make_email_parsed(email_record)
        result = await classifier.classify(email=email_parsed, email_id=email_record.id)
        assert result.category == "lead"

        # NO setear _session_id — debe hacer login automático
        assert vtiger_client._session_id is None

        with respx.mock:
            get_route = respx.get(f"{VTIGER_URL}/webservice.php")
            get_route.side_effect = _get_handler({
                "operation=getchallenge": Response(200, json={"success": True, "result": {"token": "tok-auto"}}),
                "operation=search": Response(200, json={"success": True, "result": []}),
            })

            post_route = respx.post(f"{VTIGER_URL}/webservice.php")
            post_route.side_effect = _post_handler({
                "operation=login": Response(200, json={"success": True, "result": {"sessionName": "sess-auto"}}),
                "elementType=Contacts": Response(200, json={"success": True, "result": {"id": "12x888"}}),
                "elementType=Potentials": Response(200, json={"success": True, "result": {"id": "13x999"}}),
            })

            sync_result = await sync.sync_contact(
                email_data=email_parsed,
                classification=result,
                email_record_id=email_record.id,
            )

        assert sync_result["success"] is True
        assert sync_result["contact_id"] == "12x888"
        assert sync_result["opportunity_id"] == "13x999"
        assert vtiger_client._session_id == "sess-auto"

        stmt = select(SyncLogEntry).where(SyncLogEntry.email_id == email_record.id)
        log = (await in_memory_session.execute(stmt)).scalar_one()
        assert log.status == SyncStatus.COMPLETED
