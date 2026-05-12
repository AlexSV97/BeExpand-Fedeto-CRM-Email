"""
Tests del Filter de correos.

Probamos que:
- Los emails relevantes (clientes, leads, proveedores) PASAN el filtro
- Los emails irrelevantes (OOO, auto-reply, bounce, newsletter) NO PASAN
"""

import pytest
from src.email_processor.parser import EmailParser
from src.email_processor.filter import EmailFilter
from tests.test_email_processor.samples import *


class TestEmailFilter:
    """Batería de pruebas para el EmailFilter."""

    @pytest.fixture
    def parser(self):
        return EmailParser()

    @pytest.fixture
    def email_filter(self):
        return EmailFilter()

    # ── EMAILS RELEVANTES (deben PASAR el filtro) ──

    def test_cliente_pedido_es_relevante(self, parser, email_filter):
        """Un cliente haciendo un pedido debe ser relevante."""
        parsed = parser.parse(CLIENTE_PEDIDO)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is True, f"Cliente con pedido debería ser relevante. Razón: {result.reason}"

    def test_lead_presupuesto_es_relevante(self, parser, email_filter):
        """Un lead pidiendo presupuesto debe ser relevante."""
        parsed = parser.parse(LEAD_PRESUPUESTO)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is True, f"Lead con presupuesto debería ser relevante. Razón: {result.reason}"

    def test_proveedor_factura_es_relevante(self, parser, email_filter):
        """Un proveedor enviando factura debe ser relevante."""
        parsed = parser.parse(PROVEEDOR_FACTURA)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is True, f"Proveedor con factura debería ser relevante. Razón: {result.reason}"

    def test_email_con_adjunto_es_relevante(self, parser, email_filter):
        """Un email con adjunto firmado debe ser relevante."""
        parsed = parser.parse(EMAIL_CON_ADJUNTO)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is True, f"Email con adjunto debería ser relevante. Razón: {result.reason}"

    # ── EMAILS IRRELEVANTES (deben SER FILTRADOS) ──

    def test_out_of_office_es_filtrado(self, parser, email_filter):
        """Un 'fuera de oficina' debe ser filtrado."""
        parsed = parser.parse(OUT_OF_OFFICE)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is False
        assert "fuera de oficina" in result.reason.lower() or "out of office" in result.reason.lower()

    def test_auto_reply_es_filtrado(self, parser, email_filter):
        """Una respuesta automática debe ser filtrada."""
        parsed = parser.parse(AUTO_REPLY)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is False

    def test_newsletter_es_filtrado(self, parser, email_filter):
        """Un newsletter debe ser filtrado."""
        parsed = parser.parse(NEWSLETTER)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is False
        assert "newsletter" in result.reason.lower() or "baja" in result.reason.lower() or "suscrito" in result.reason.lower()

    def test_bounce_es_filtrado(self, parser, email_filter):
        """Un bounce (fallo de entrega) debe ser filtrado."""
        parsed = parser.parse(BOUNCE)
        result = email_filter.evaluate(parsed)

        assert result.is_relevant is False
        # Se filtra por remitente (mailer-daemon@ionos.es) ANTES de
        # llegar a la regla de bounce — el resultado final es el mismo
        assert "mailer-daemon" in result.reason.lower() or "bounce" in result.reason.lower()

    # ── PRUEBAS DE LÍMITE ──

    def test_none_email_no_es_relevante(self, email_filter):
        """Un email None debe ser filtrado por seguridad."""
        result = email_filter.evaluate(None)

        assert result.is_relevant is False
        assert "nulo" in result.reason.lower()

    def test_filter_result_repr(self, email_filter):
        """Verificar que el repr de FilterResult funciona."""
        from src.email_processor.filter import FilterResult

        r1 = FilterResult(True, "")
        r2 = FilterResult(False, "Spam detectado")

        assert "Relevante" in repr(r1)
        assert "Filtrado" in repr(r2)
        assert "Spam" in repr(r2)
