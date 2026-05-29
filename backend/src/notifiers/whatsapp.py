"""
WhatsAppNotifier — envía alertas de correos urgentes vía Twilio WhatsApp API.

Usa la API REST de Twilio vía httpx (sin dependencias adicionales).

Configuración necesaria en .env:
    TWILIO_ACCOUNT_SID=ACxxx...  (de tu consola Twilio)
    TWILIO_AUTH_TOKEN=xxx...     (de tu consola Twilio)
    TWILIO_FROM_NUMBER=+14155238886  (sandbox) o tu número aprobado
    TWILIO_TO_NUMBER=+34600123456     (destinatario)
    TWILIO_MIN_URGENCY=alta

Sandbox de prueba (GRATIS):
    1. Regístrate en https://twilio.com
    2. Ve a Messaging → Try it out → Send a WhatsApp message
    3. Te dan un número sandbox (+14155238886) y una palabra clave
    4. Desde tu móvil, envía "join <palabra>" al número sandbox
    5. ¡Ya puedes recibir mensajes!
"""

import logging
from base64 import b64encode

from src.config import get_settings

logger = logging.getLogger(__name__)

_URGENCY_SCALE = {"alta": 3, "media": 2, "baja": 1}


class WhatsAppNotifier:
    """Notificador de correos urgentes vía Twilio WhatsApp API."""

    def __init__(self, settings=None):
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        """El notificador está operativo si hay credenciales y números configurados."""
        return bool(
            self._settings.twilio_account_sid
            and self._settings.twilio_auth_token
            and self._settings.twilio_from_number
            and self._settings.twilio_to_number
        )

    def _should_notify(self, urgency: str) -> bool:
        """Comprueba si la urgencia del correo supera el umbral mínimo."""
        min_urgency = self._settings.twilio_min_urgency
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
        """Construye el mensaje de texto plano (WhatsApp no soporta Markdown)."""
        lines = [
            "⚠️ CORREO URGENTE - BeConnect",
            "",
            f"Asunto: {subject or '(sin asunto)'}",
            f"De: {sender_name} <{sender_email}>",
            f"Urgencia: {urgency.upper()}",
            f"Categoría: {category}",
        ]
        if summary:
            lines.append(f"Resumen: {summary}")
        if action_required:
            lines.append(f"Acción: {action_required}")
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
        """Envía una alerta a WhatsApp si la urgencia supera el umbral configurado.

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
            logger.debug("Twilio WhatsApp no configurado — omitiendo alerta")
            return False

        if not self._should_notify(urgency):
            logger.debug("Urgencia '%s' por debajo del umbral '%s' — omitiendo alerta",
                         urgency, self._settings.twilio_min_urgency)
            return False

        try:
            import httpx

            text = self._build_message(
                subject, sender_name, sender_email,
                urgency, category, summary, action_required,
            )

            account_sid = self._settings.twilio_account_sid
            auth_token = self._settings.twilio_auth_token
            from_number = self._settings.twilio_from_number
            to_number = self._settings.twilio_to_number

            # Auth: Basic base64(account_sid:auth_token)
            auth_header = b64encode(f"{account_sid}:{auth_token}".encode()).decode()

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "To": f"whatsapp:{to_number}",
                        "From": f"whatsapp:{from_number}",
                        "Body": text,
                    },
                )
                result = response.json()

            if response.status_code in (200, 201) and result.get("sid"):
                logger.info("Alerta WhatsApp enviada (Twilio): %s", subject)
                return True

            logger.warning("Twilio API error: %s", result.get("message", result))
            return False

        except ImportError:
            logger.warning("httpx no disponible — no se puede enviar alerta WhatsApp")
            return False
        except Exception as e:
            logger.error("Error enviando alerta WhatsApp (Twilio): %s", e)
            return False
