"""
Tests para VtigerClient — simula llamadas HTTP con respx.

respx intercepta las llamadas a httpx y devuelve respuestas falsas.
No se necesita un servidor VTiger real.
"""

import pytest
import respx
from httpx import Response

from src.crm.vtiger_client import VtigerClient, VtigerAuthError


@pytest.fixture
def client():
    """Crea un VtigerClient apuntando a una URL falsa."""
    return VtigerClient(
        url="https://falso.vtiger.com",
        username="admin@test.com",
        access_key="abc123",
    )


@pytest.fixture
def logged_client(client):
    """Cliente con sesión ya iniciada (saltea login())."""
    client._session_id = "session-pre-auth"
    return client


class TestVtigerClientLogin:
    """Tests del flujo de autenticación."""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Login exitoso: challenge + login → sessionId."""
        with respx.mock:
            # GET getchallenge → token
            respx.get("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"token": "abc123", "serverTime": "123"}}
            )
            # POST login → sessionId
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"sessionName": "session-xyz"}}
            )

            session_id = await client.login()

        assert session_id == "session-xyz"
        assert client._session_id == "session-xyz"

    @pytest.mark.asyncio
    async def test_login_getchallenge_fails(self, client):
        """Si getchallenge da error HTTP, login lanza excepción."""
        with respx.mock:
            respx.get("https://falso.vtiger.com/webservice.php").respond(500)

            with pytest.raises(Exception):
                await client.login()

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client):
        """Credenciales inválidas → VtigerAuthError."""
        with respx.mock:
            respx.get("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"token": "abc123"}}
            )
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": False, "error": {"message": "Invalid credentials"}}
            )

            with pytest.raises(VtigerAuthError):
                await client.login()


class TestVtigerClientContacts:
    """Tests de operaciones con contactos (usando sesión pre-autenticada)."""

    @pytest.mark.asyncio
    async def test_create_contact_success(self, logged_client):
        """Crear contacto → devuelve el ID de VTiger."""
        with respx.mock:
            # La llamada POST es para create_contact
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"id": "12x34"}}
            )

            contact_id = await logged_client.create_contact({
                "email": "test@test.com",
                "lastname": "Test",
            })

        assert contact_id == "12x34"

    @pytest.mark.asyncio
    async def test_get_contact_exists(self, logged_client):
        """Buscar contacto existente → devuelve sus datos."""
        with respx.mock:
            respx.get("https://falso.vtiger.com/webservice.php").respond(
                json={
                    "success": True,
                    "result": [{"id": "12x34", "email": "test@test.com", "lastname": "Test"}],
                }
            )

            result = await logged_client.get_contact_by_email("test@test.com")

        assert result is not None
        assert result["id"] == "12x34"
        assert result["email"] == "test@test.com"

    @pytest.mark.asyncio
    async def test_get_contact_not_found(self, logged_client):
        """Buscar contacto inexistente → devuelve None."""
        with respx.mock:
            respx.get("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": []}
            )

            result = await logged_client.get_contact_by_email("noexiste@test.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_contact_success(self, logged_client):
        """Actualizar contacto → devuelve True."""
        with respx.mock:
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"id": "12x34"}}
            )

            result = await logged_client.update_contact("12x34", {"lastname": "Nuevo"})

        assert result is True

    @pytest.mark.asyncio
    async def test_update_contact_not_found(self, logged_client):
        """Si VTiger reporta error al actualizar, devuelve False."""
        with respx.mock:
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": False, "error": {"message": "Record not found"}}
            )

            result = await logged_client.update_contact("99x99", {"lastname": "Nuevo"})

        assert result is False


class TestVtigerClientOpportunities:
    """Tests de operaciones con oportunidades."""

    @pytest.mark.asyncio
    async def test_create_opportunity_success(self, logged_client):
        """Crear oportunidad → devuelve el ID."""
        with respx.mock:
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": True, "result": {"id": "13x56"}}
            )

            opp_id = await logged_client.create_opportunity({
                "potentialname": "Lead: Test",
                "related_to": "12x34",
            })

        assert opp_id == "13x56"

    @pytest.mark.asyncio
    async def test_create_opportunity_fails_gracefully(self, logged_client):
        """Si VTiger falla al crear oportunidad, devuelve None."""
        with respx.mock:
            respx.post("https://falso.vtiger.com/webservice.php").respond(
                json={"success": False, "error": {"message": "Module not permitted"}}
            )

            opp_id = await logged_client.create_opportunity({
                "potentialname": "Lead: Test",
                "related_to": "12x34",
            })

        assert opp_id is None
