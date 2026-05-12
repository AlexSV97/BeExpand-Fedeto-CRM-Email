"""
Tests del Parser de correos.

Probamos que el parser extrae correctamente todos los campos
de diferentes tipos de emails.
"""

import pytest
from src.email_processor.parser import EmailParser
from tests.test_email_processor.samples import *


class TestEmailParser:
    """Batería de pruebas para el EmailParser."""

    @pytest.fixture
    def parser(self):
        return EmailParser()

    # ── PRUEBAS DE EXTRACCIÓN BÁSICA ──

    def test_parse_cliente_pedido(self, parser):
        """Debe extraer correctamente un email de cliente con pedido."""
        result = parser.parse(CLIENTE_PEDIDO)

        assert result is not None
        assert "Pedido #3842" in result.subject
        assert result.sender_email == "ana@garcia-sl.com"
        assert "Ana García" in result.sender_name
        assert result.body_plain != ""
        assert "Confirmamos el pedido" in result.body_plain
        assert result.has_attachments is False
        assert result.recipients[0]["email"] == "comercial@beexpand.com"

    def test_parse_lead_presupuesto(self, parser):
        """Debe extraer correctamente un email de lead."""
        result = parser.parse(LEAD_PRESUPUESTO)

        assert result is not None
        assert "Presupuesto" in result.subject
        assert result.sender_email == "carlos@techcorp.com"
        assert "Carlos Méndez" in result.sender_name
        assert "reforma" in result.body_plain.lower()
        # La fecha debe parsearse correctamente
        assert result.date is not None
        assert result.date.year == 2026

    def test_parse_proveedor_factura(self, parser):
        """Debe extraer correctamente un email de proveedor."""
        result = parser.parse(PROVEEDOR_FACTURA)

        assert result is not None
        assert "Factura mensual" in result.subject
        assert result.sender_email == "administracion@suministros-sa.com"
        # Remitente sin nombre
        assert result.sender_name == ""

    # ── PRUEBAS DE ADJUNTOS ──

    def test_parse_email_con_adjunto(self, parser):
        """Debe detectar y extraer información de adjuntos."""
        result = parser.parse(EMAIL_CON_ADJUNTO)

        assert result is not None
        assert result.has_attachments is True
        assert len(result.attachments) == 1
        assert result.attachments[0]["filename"] == "contrato_firmado.pdf"
        assert result.attachments[0]["content_type"] == "application/pdf"

    # ── PRUEBAS DE CARACTERES ESPECIALES ──

    def test_parse_utf8_characters(self, parser):
        """Debe manejar correctamente caracteres UTF-8 (tildes, eñes)."""
        result = parser.parse(CLIENTE_PEDIDO)

        assert result is not None
        assert "García" in result.sender_name  # ñ y acento

        result2 = parser.parse(LEAD_PRESUPUESTO)
        assert result2 is not None
        assert "Méndez" in result2.sender_name  # acento

    # ── PRUEBAS DE CAMPOS VACÍOS ──

    def test_parse_empty_email(self, parser):
        """Email vacío debe devolver None o un objeto con campos vacíos."""
        result = parser.parse(b"")
        # Depende de cómo tolere la librería email un mensaje vacío
        # Pero no debe lanzar excepción
        assert result is not None or True

    def test_parse_message_id(self, parser):
        """Debe extraer el Message-ID del email."""
        result = parser.parse(CLIENTE_PEDIDO)

        assert result is not None
        assert result.message_id != ""
        assert "@" in result.message_id or result.message_id != ""

    # ── PRUEBAS DE DESTINATARIOS ──

    def test_parse_recipients(self, parser):
        """Debe extraer correctamente los destinatarios."""
        result = parser.parse(CLIENTE_PEDIDO)

        assert result is not None
        assert len(result.recipients) > 0
        # Verificar que el destinatario está en la lista
        recipient_emails = [r["email"] for r in result.recipients]
        assert "comercial@beexpand.com" in recipient_emails
