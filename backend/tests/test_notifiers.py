"""
Tests del módulo de notificaciones (TelegramNotifier).

Cubre:
- enabled / disabled según configuración
- Filtro por umbral de urgencia
- Formateo del mensaje
- Envío real (mockeado) y manejo de errores
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifiers.telegram import TelegramNotifier


class MockSettings:
    """Settings mínimos para testing."""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_min_urgency: str = "alta"


class TestTelegramNotifierEnabled:
    """Propiedad enabled — depende de token + chat_id."""

    def test_disabled_when_no_token(self):
        settings = MockSettings()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = "123"
        assert TelegramNotifier(settings).enabled is False

    def test_disabled_when_no_chat_id(self):
        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = ""
        assert TelegramNotifier(settings).enabled is False

    def test_enabled_when_both_present(self):
        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = "123456"
        assert TelegramNotifier(settings).enabled is True


class TestTelegramNotifierShouldNotify:
    """Filtro por umbral de urgencia (_should_notify)."""

    def test_alta_notifies_when_threshold_is_alta(self):
        settings = MockSettings()
        settings.telegram_min_urgency = "alta"
        notifier = TelegramNotifier(settings)
        assert notifier._should_notify("alta") is True
        assert notifier._should_notify("media") is False
        assert notifier._should_notify("baja") is False

    def test_media_notifies_when_threshold_is_media(self):
        settings = MockSettings()
        settings.telegram_min_urgency = "media"
        notifier = TelegramNotifier(settings)
        assert notifier._should_notify("alta") is True
        assert notifier._should_notify("media") is True
        assert notifier._should_notify("baja") is False

    def test_baja_notifies_when_threshold_is_baja(self):
        settings = MockSettings()
        settings.telegram_min_urgency = "baja"
        notifier = TelegramNotifier(settings)
        assert notifier._should_notify("alta") is True
        assert notifier._should_notify("media") is True
        assert notifier._should_notify("baja") is True

    def test_unknown_urgency_does_not_notify(self):
        settings = MockSettings()
        notifier = TelegramNotifier(settings)
        assert notifier._should_notify("desconocida") is False


class TestTelegramNotifierBuildMessage:
    """Formateo del mensaje Markdown."""

    def test_basic_message(self):
        settings = MockSettings()
        notifier = TelegramNotifier(settings)
        msg = notifier._build_message(
            subject="Factura urgente",
            sender_name="Proveedor SL",
            sender_email="facturas@proveedor.com",
            urgency="alta",
            category="proveedor",
        )
        assert "🚨" in msg
        assert "Factura urgente" in msg
        assert "Proveedor SL" in msg
        assert "ALTA" in msg
        assert "proveedor" in msg

    def test_with_summary_and_action(self):
        settings = MockSettings()
        notifier = TelegramNotifier(settings)
        msg = notifier._build_message(
            subject="Reunión mañana",
            sender_name="Cliente SA",
            sender_email="cliente@sa.com",
            urgency="alta",
            category="cliente",
            summary="Confirma reunión del jueves a las 10",
            action_required="reunion",
        )
        assert "Resumen" in msg
        assert "Confirma reunión" in msg
        assert "Acción requerida" in msg
        assert "reunion" in msg


class TestTelegramNotifierSend:
    """Envío real con httpx mockeado."""

    @patch("httpx.AsyncClient")
    async def test_send_alert_success(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = "123456"

        notifier = TelegramNotifier(settings)
        result = await notifier.send_alert(
            subject="Factura urgente",
            sender_name="Proveedor SL",
            sender_email="facturas@proveedor.com",
            urgency="alta",
            category="proveedor",
        )

        assert result is True
        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert "bot123:abc" in args[0]
        assert kwargs["json"]["chat_id"] == "123456"
        assert "Factura urgente" in kwargs["json"]["text"]

    async def test_send_alert_when_disabled(self):
        settings = MockSettings()  # token vacío → disabled
        notifier = TelegramNotifier(settings)
        result = await notifier.send_alert(
            subject="Test",
            sender_name="Test",
            sender_email="test@test.com",
            urgency="alta",
            category="test",
        )
        assert result is False

    async def test_send_alert_below_threshold(self):
        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = "123456"
        settings.telegram_min_urgency = "alta"

        notifier = TelegramNotifier(settings)
        result = await notifier.send_alert(
            subject="Test",
            sender_name="Test",
            sender_email="test@test.com",
            urgency="baja",
            category="test",
        )
        assert result is False

    @patch("httpx.AsyncClient")
    async def test_send_alert_api_error(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "chat not found"}
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = "999999"

        notifier = TelegramNotifier(settings)
        result = await notifier.send_alert(
            subject="Test",
            sender_name="Test",
            sender_email="test@test.com",
            urgency="alta",
            category="test",
        )
        assert result is False

    @patch("httpx.AsyncClient")
    async def test_send_alert_network_error(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = Exception("Connection timeout")

        settings = MockSettings()
        settings.telegram_bot_token = "bot123:abc"
        settings.telegram_chat_id = "123456"

        notifier = TelegramNotifier(settings)
        result = await notifier.send_alert(
            subject="Test",
            sender_name="Test",
            sender_email="test@test.com",
            urgency="alta",
            category="test",
        )
        assert result is False
