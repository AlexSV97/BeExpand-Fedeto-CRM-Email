"""
TelegramNotifier — envía alertas de correos urgentes a Telegram.

Usa la Bot API de Telegram vía httpx (sin dependencias adicionales).
Token → @BotFather en Telegram (crea un bot y obtén el token).
Chat ID → envía un mensaje al bot y consulta getUpdates:

    curl https://api.telegram.org/bot<TOKEN>/getUpdates
"""

import logging

from src.config import get_settings

logger = logging.getLogger(__name__)

# Escala de urgencia para filtrar notificaciones
_URGENCY_SCALE = {"alta": 3, "media": 2, "baja": 1}


class TelegramNotifier:
    """Notificador de correos urgentes vía Telegram Bot API."""

    def __init__(self, settings=None):
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        """El notificador está operativo si hay token y chat_id configurados."""
        return bool(self._settings.telegram_bot_token and self._settings.telegram_chat_id)

    def _should_notify(self, urgency: str) -> bool:
        """Comprueba si la urgencia del correo supera el umbral mínimo."""
        min_urgency = self._settings.telegram_min_urgency
        level = _URGENCY_SCALE.get(urgency, 0)
        threshold = _URGENCY_SCALE.get(min_urgency, 3)
        return level >= threshold

    def _build_message(
        self,
        subject: str,
        sender_name: str,
        sender_email: str,
        urgency: str,
        category: str,
        summary: str | None = None,
        action_required: str | None = None,
    ) -> str:
        """Construye el mensaje formateado en Markdown."""
        lines = [
            f"🚨 *Correo urgente*",
            f"",
            f"*Asunto:* {subject or '(sin asunto)'}",
            f"*De:* {sender_name} <{sender_email}>",
            f"*Urgencia:* {urgency.upper()}",
            f"*Categoría:* {category}",
        ]
        if summary:
            lines.append("")
            lines.append(f"*Resumen:* {summary}")
        if action_required:
            lines.append(f"*Acción requerida:* {action_required}")
        return "\n".join(lines)

    async def send_alert(
        self,
        subject: str,
        sender_name: str,
        sender_email: str,
        urgency: str,
        category: str,
        summary: str | None = None,
        action_required: str | None = None,
    ) -> bool:
        """Envía una alerta a Telegram si la urgencia supera el umbral configurado.

        Args:
            subject: Asunto del correo.
            sender_name: Nombre del remitente.
            sender_email: Email del remitente.
            urgency: Nivel de urgencia (alta/media/baja).
            category: Categoría asignada (cliente/lead/proveedor).
            summary: Resumen ejecutivo (opcional).
            action_required: Acción requerida detectada (opcional).

        Returns:
            True si se envió correctamente, False en caso contrario.
        """
        if not self.enabled:
            return False

        if not self._should_notify(urgency):
            logger.debug("Urgencia '%s' por debajo del umbral '%s' — omitiendo alerta",
                         urgency, self._settings.telegram_min_urgency)
            return False

        try:
            import httpx

            token = self._settings.telegram_bot_token
            chat_id = self._settings.telegram_chat_id
            text = self._build_message(
                subject, sender_name, sender_email,
                urgency, category, summary, action_required,
            )

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                response.raise_for_status()
                result = response.json()

            if result.get("ok"):
                logger.info("Alerta Telegram enviada: %s", subject)
                return True

            logger.warning("Telegram API error: %s", result.get("description"))
            return False

        except ImportError:
            logger.warning("httpx no disponible — no se puede enviar alerta Telegram")
            return False
        except Exception as e:
            logger.error("Error enviando alerta Telegram: %s", e)
            return False
