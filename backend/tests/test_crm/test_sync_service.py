"""
Tests para CrmSyncService — orquestación de la sincronización con VTiger.

CrmSyncService coordina:
  1. Buscar/crear/actualizar contacto en VTiger
  2. Si es Lead → crear oportunidad
  3. Registrar todo en SyncLogEntry

Mockeamos VtigerClient y AsyncSession para aislar la lógica de orquestación.

SyncLogEntry y SyncStatus no están implementados aún en models.py,
así que los creamos como stubs y parcheamos el import.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.interfaces import ClassificationResult


# ── Stubs para modelos que todavía no existen en src.db.models ──


class SyncStatus:
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass
class SyncLogEntry:
    email_id: str = ""
    status: str = ""
    details: dict = None


# Parches que se aplican ANTES de importar sync_service
SYNC_PATCHES = [
    patch("src.db.models.SyncLogEntry", SyncLogEntry, create=True),
    patch("src.db.models.SyncStatus", SyncStatus, create=True),
]


def _apply_patches():
    """Aplica todos los parches de sync y devuelve el cleanup."""
    for p in SYNC_PATCHES:
        p.start()


def _cleanup_patches():
    for p in SYNC_PATCHES:
        p.stop()


# ── Fixtures compartidos ──


@pytest.fixture(autouse=True)
def _patch_sync_models():
    """Parchea SyncLogEntry y SyncStatus antes de cada test."""
    _apply_patches()
    yield
    _cleanup_patches()


@pytest.fixture
def email_data():
    """EmailParsed típico de un lead comercial."""
    return EmailParsed(
        message_id="msg-001",
        subject="Cotización de materiales para construcción",
        body_plain="Necesito cotización de 500 bolsas de cemento...",
        sender_email="cliente@constructora.com",
        sender_name="Carlos Méndez",
        recipients=[{"email": "ventas@fedeto.com", "name": "Ventas Fedeto", "type": "to"}],
    )


@pytest.fixture
def classification_cliente():
    """Clasificación como cliente existente."""
    return ClassificationResult(
        category="cliente",
        confidence=0.95,
        method="rule_engine",
        details={"matched_keyword": "cliente"},
    )


@pytest.fixture
def classification_lead():
    """Clasificación como lead (nuevo oportunidad)."""
    return ClassificationResult(
        category="lead",
        confidence=0.85,
        method="rule_engine",
        details={"matched_keyword": "presupuesto"},
    )


@pytest.fixture
def classification_proveedor():
    """Clasificación como proveedor."""
    return ClassificationResult(
        category="proveedor",
        confidence=0.75,
        method="rule_engine",
        details={"matched_keyword": "proveedor"},
    )


@pytest.fixture
def classification_otro():
    """Clasificación que NO requiere sincronización."""
    return ClassificationResult(
        category="nulo",
        confidence=0.6,
        method="rule_engine",
        details={"reason": "no_match"},
    )


@pytest.fixture
def mock_vtiger():
    """VtigerClient completamente mockeado."""
    client = MagicMock()
    client._session_id = None
    client.login = AsyncMock()
    client.get_contact_by_email = AsyncMock()
    client.create_contact = AsyncMock()
    client.update_contact = AsyncMock()
    client.create_opportunity = AsyncMock()
    return client


@pytest.fixture
def mock_db_session():
    """AsyncSession mockeada."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


# ── Tests de sync_contact ──


class TestSyncContactSkipped:
    """Tests: categorías que no requieren sincronización."""

    @pytest.mark.asyncio
    async def test_skips_non_sync_category(self, email_data, classification_otro, mock_vtiger, mock_db_session):
        """Categoría 'nulo' → devuelve skipped sin tocar VTiger."""
        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_otro,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["action"] == "skipped"
        assert result["contact_id"] is None
        assert result["opportunity_id"] is None
        mock_vtiger.login.assert_not_called()
        mock_vtiger.get_contact_by_email.assert_not_called()
        mock_db_session.add.assert_not_called()


class TestSyncContactCliente:
    """Tests: categoría 'cliente' — solo upsert contacto."""

    @pytest.mark.asyncio
    async def test_creates_new_contact(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Cliente nuevo en VTiger → crea contacto, registra COMPLETED."""
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = "12x100"

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["action"] == "created"
        assert result["contact_id"] == "12x100"
        assert result["opportunity_id"] is None
        mock_vtiger.login.assert_awaited_once()
        mock_vtiger.get_contact_by_email.assert_awaited_once_with("cliente@constructora.com")
        mock_vtiger.create_contact.assert_awaited_once()
        mock_vtiger.update_contact.assert_not_called()
        mock_vtiger.create_opportunity.assert_not_called()
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_updates_existing_contact(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Cliente existente en VTiger → actualiza contacto, registra COMPLETED."""
        mock_vtiger.get_contact_by_email.return_value = {"id": "12x50", "email": "cliente@constructora.com"}
        mock_vtiger.update_contact.return_value = True

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["contact_id"] == "12x50"
        mock_vtiger.login.assert_awaited_once()
        mock_vtiger.get_contact_by_email.assert_awaited_once_with("cliente@constructora.com")
        mock_vtiger.update_contact.assert_awaited_once()
        mock_vtiger.create_contact.assert_not_called()
        mock_vtiger.create_opportunity.assert_not_called()
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_contact_exists_but_no_id(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Contacto existe pero sin ID en VTiger → no falla estrepitosamente."""
        mock_vtiger.get_contact_by_email.return_value = {"name": "Carlos Méndez"}  # sin 'id'

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["contact_id"] is None  # no se pudo obtener ID
        mock_vtiger.update_contact.assert_not_called()


class TestSyncContactLead:
    """Tests: categoría 'lead' — upsert contacto + crear oportunidad."""

    @pytest.mark.asyncio
    async def test_creates_contact_and_opportunity(self, email_data, classification_lead, mock_vtiger, mock_db_session):
        """Lead nuevo → crea contacto Y oportunidad."""
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = "12x200"
        mock_vtiger.create_opportunity.return_value = "13x100"

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_lead,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["contact_id"] == "12x200"
        assert result["opportunity_id"] == "13x100"
        assert result["action"] == "created"
        mock_vtiger.create_contact.assert_awaited_once()
        mock_vtiger.create_opportunity.assert_awaited_once()
        call_kwargs = mock_vtiger.create_opportunity.call_args[0][0]
        assert call_kwargs["related_to"] == "12x200"
        assert "Lead:" in call_kwargs["potentialname"]

    @pytest.mark.asyncio
    async def test_lead_without_contact_skips_opportunity(self, email_data, classification_lead, mock_vtiger, mock_db_session):
        """Si crear contacto falla, NO debe intentar crear oportunidad."""
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = None  # falla

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_lead,
            email_record_id="email-001",
        )

        assert result["contact_id"] is None
        assert result["opportunity_id"] is None
        mock_vtiger.create_opportunity.assert_not_called()


class TestSyncContactError:
    """Tests: manejo de errores de VTiger."""

    @pytest.mark.asyncio
    async def test_auth_error_logs_failed(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """VtigerAuthError → success=False, action=error, log FAILED."""
        from src.crm.vtiger_client import VtigerAuthError
        mock_vtiger.login.side_effect = VtigerAuthError("Credenciales inválidas")

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is False
        assert result["action"] == "error"
        assert result["contact_id"] is None
        assert mock_db_session.add.called
        mock_db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_connection_error_logs_failed(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """VtigerClientError → success=False, action=error, log FAILED."""
        from src.crm.vtiger_client import VtigerClientError
        mock_vtiger.login.side_effect = VtigerClientError("VTiger no disponible")

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is False
        assert result["action"] == "error"
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_get_contact_failure_still_creates_contact(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Si get_contact_by_email falla (None), debe intentar crear."""
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = "12x300"

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["contact_id"] == "12x300"
        assert result["action"] == "created"
        mock_vtiger.create_contact.assert_awaited_once()


class TestSyncContactProveedor:
    """Tests: categoría 'proveedor' — upsert contacto, sin oportunidad."""

    @pytest.mark.asyncio
    async def test_creates_proveedor_contact(self, email_data, classification_proveedor, mock_vtiger, mock_db_session):
        """Proveedor nuevo → crea contacto, NO crea oportunidad."""
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = "12x400"

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_proveedor,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["contact_id"] == "12x400"
        assert result["opportunity_id"] is None
        mock_vtiger.create_contact.assert_awaited_once()
        mock_vtiger.create_opportunity.assert_not_called()


class TestSyncContactAutoLogin:
    """Tests: login automático cuando no hay sesión activa."""

    @pytest.mark.asyncio
    async def test_logs_in_when_no_session(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Sin session_id → hace login automático."""
        mock_vtiger._session_id = None
        mock_vtiger.get_contact_by_email.return_value = None
        mock_vtiger.create_contact.return_value = "12x500"

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        assert result["contact_id"] == "12x500"
        mock_vtiger.login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_login_when_session_active(self, email_data, classification_cliente, mock_vtiger, mock_db_session):
        """Con session_id activo → NO llama login()."""
        mock_vtiger._session_id = "session-activa"
        mock_vtiger.get_contact_by_email.return_value = {"id": "12x600"}
        mock_vtiger.update_contact.return_value = True

        from src.crm.sync_service import CrmSyncService

        service = CrmSyncService(vtiger_client=mock_vtiger, db_session=mock_db_session)
        result = await service.sync_contact(
            email_data=email_data,
            classification=classification_cliente,
            email_record_id="email-001",
        )

        assert result["success"] is True
        mock_vtiger.login.assert_not_called()
