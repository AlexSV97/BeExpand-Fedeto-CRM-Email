"""
WhatsAppNotifier — envía alertas de correos urgentes vía WhatsApp Business API.

Usa la Meta WhatsApp Cloud API vía httpx (sin dependencias adicionales).

Configuración necesaria en .env:
    WHATSAPP_ACCESS_TOKEN=EAAT...  (token de acceso de Meta)
    WHATSAPP_PHONE_NUMBER_ID=123456789  (ID del número emisor)
    WHATSAPP_TO_PHONE=34600123456  (destinatario, formato internacional sin +)
    WHATSAPP_MIN_URGENCY=alta  (umbral: alta | media | baja)

Para obtener las credenciales:
    1. Crea/usa una Meta Business Account (business.facebook.com)
    2. Crea una WhatsApp Business Account
    3. Registra un número de teléfono (verificación con código SMS)
    4. Genera un token de acceso permanente desde:
       business.facebook.com → WhatsApp → API Setup
    5. El phone_number_id aparece en la misma página
"""

import logging

from src.config import get_settings

logger = logging.getLogger(__name__)

_URGENCY_SCALE = {"alta": 3, "media": 2, "baja": 1}


class WhatsAppNotifier:
    """Notificador de correos urgentes vía Meta WhatsApp Cloud API."""

    def __init__(self, settings=None):
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        """El notificador está operativo si hay token y destinatario configurados."""
        return bool(
            self._settings.whatsapp_access_token
            and self._settings.whatsapp_phone_number_id
            and self._settings.whatsapp_to_phone
        )

    def _should_notify(self, urgency: str) -> bool:
        """Comprueba si la urgencia del correo supera el umbral mínimo."""
        min_urgency = self._settings.whatsapp_min_urgency
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
        """Construye el mensaje de texto plano (WhatsApp no soporta Markdown completo)."""
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
            logger.debug("WhatsApp no configurado — omitiendo alerta")
            return False

        if not self._should_notify(urgency):
            logger.debug("Urgencia '%s' por debajo del umbral '%s' — omitiendo alerta",
                         urgency, self._settings.whatsapp_min_urgency)
            return False

        try:
            import httpx

            token = self._settings.whatsapp_access_token
            phone_number_id = self._settings.whatsapp_phone_number_id
            to_phone = self._settings.whatsapp_to_phone
            text = self._build_message(
                subject, sender_name, sender_email,
                urgency, category, summary, action_required,
            )

            url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": to_phone,
                        "type": "text",
                        "text": {"body": text},
                    },
                )
                response.raise_for_status()
                result = response.json()

            if result.get("messages"):
                logger.info("Alerta WhatsApp enviada: %s", subject)
                return True

            logger.warning("WhatsApp API error: %s", result.get("error", result))
            return False

        except ImportError:
            logger.warning("httpx no disponible — no se puede enviar alerta WhatsApp")
            return False
        except Exception as e:
            logger.error("Error enviando alerta WhatsApp: %s", e)
            return False
