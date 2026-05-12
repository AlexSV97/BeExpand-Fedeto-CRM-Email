"""
Tests del IMAP Connector.

Como no tenemos acceso a un servidor IMAP real,
usamos mocking para simular las respuestas del servidor.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.email_processor.imap_connector import IMAPConnector


class TestIMAPConnector:
    """Batería de pruebas para el IMAPConnector usando mocks."""

    @pytest.fixture
    def connector(self):
        """Crea un conector con datos de prueba."""
        return IMAPConnector(
            host="imap.ionos.es",
            port=993,
            username="test@beexpand.com",
            password="test123",
            use_ssl=True,
        )

    # ── PRUEBAS DE CONEXIÓN ──

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_connect_success(self, mock_imap, connector):
        """Conectar debe funcionar con credenciales válidas."""
        # Configurar el mock para que login devuelva OK
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_imap.return_value = mock_instance

        result = connector.connect()

        assert result is True
        assert connector.connection is not None
        # Verificar que se llamó a login con las credenciales correctas
        mock_instance.login.assert_called_once_with("test@beexpand.com", "test123")

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_connect_failure(self, mock_imap, connector):
        """Conectar debe fallar con credenciales inválidas."""
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception("Authentication failed")
        mock_imap.return_value = mock_instance

        result = connector.connect()

        assert result is False

    # ── PRUEBAS DE CIERRE ──

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_logout(self, mock_imap, connector):
        """Logout debe cerrar la conexión."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_imap.return_value = mock_instance

        connector.connect()
        connector.logout()

        mock_instance.logout.assert_called_once()
        assert connector.connection is None

    # ── PRUEBAS DE BÚSQUEDA ──

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_fetch_unread_no_emails(self, mock_imap, connector):
        """Sin emails nuevos, debe devolver lista vacía."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_instance.select.return_value = ("OK", [b"1"])
        # Simular que no hay emails no leídos
        mock_instance.search.return_value = ("OK", [b""])
        mock_imap.return_value = mock_instance

        connector.connect()
        emails = connector.fetch_unread()

        assert emails == []

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_fetch_unread_with_emails(self, mock_imap, connector):
        """Con emails nuevos, debe devolverlos."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_instance.select.return_value = ("OK", [b"1"])
        mock_instance.search.return_value = ("OK", [b"1 2 3"])

        # Simular que cada fetch devuelve un email
        def fetch_side_effect(uid, *args):
            return ("OK", [(b"1 (RFC822)", b"Subject: Test\r\n\r\nBody"), b")"])

        mock_instance.fetch.side_effect = fetch_side_effect
        mock_imap.return_value = mock_instance

        connector.connect()
        emails = connector.fetch_unread()

        assert len(emails) == 3
        assert all(isinstance(e, bytes) for e in emails)

    # ── PRUEBAS DE MARCADO ──

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_mark_as_seen(self, mock_imap, connector):
        """Marcar como leído debe llamar a store con +FLAGS \\Seen."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_instance.store.return_value = ("OK", [b""])
        mock_imap.return_value = mock_instance

        connector.connect()
        result = connector.mark_as_seen(b"1")

        assert result is True
        mock_instance.store.assert_called_with(b"1", "+FLAGS", "\\Seen")

    # ── PRUEBAS DE VERIFICACIÓN DE CONEXIÓN ──

    @patch("src.email_processor.imap_connector.imaplib.IMAP4_SSL")
    def test_is_connected(self, mock_imap, connector):
        """is_connected debe detectar si la conexión está viva."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_imap.return_value = mock_instance

        connector.connect()
        assert connector.is_connected() is True

        # Simular conexión perdida
        mock_instance.noop.side_effect = Exception("Connection lost")
        assert connector.is_connected() is False
