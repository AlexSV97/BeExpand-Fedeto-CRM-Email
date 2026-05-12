"""
Filtro de Correos — Separación de emails relevantes e irrelevantes.

¿Qué hace?
Determina si un email merece ser procesado o debe descartarse.

Descarta:
- ❌ Fuera de oficina / vacaciones
- ❌ Notificaciones de entrega (bounce)
- ❌ Spam / correo masivo
- ❌ Newsletters no solicitados
- ❌ Respuestas automáticas
- ❌ Emails de sistemas (noreply, mailer-daemon)

NO descarta (pasa al clasificador):
- ✅ Correos de clientes
- ✅ Correos de leads / potenciales clientes
- ✅ Correos de proveedores
- ✅ Cualquier correo de un humano a otro humano
"""

import logging
import re
from typing import Optional

from src.email_processor.parser import EmailParsed

logger = logging.getLogger(__name__)


class EmailFilter:
    """
    Evalúa si un email es relevante o debe filtrarse.

    El filtro es configurable: se pueden añadir o quitar reglas
    sin cambiar el código (patrón de composición).

    Uso:
        filter = EmailFilter()
        result = filter.evaluate(parsed_email)
        if result.is_relevant:
            # Pasa al clasificador
        else:
            # Descartar o marcar como irrelevante
    """

    # ── PATRONES PARA DETECTAR EMAILS IRRELEVANTES ──

    # Fuera de oficina (en varios idiomas)
    OUT_OF_OFFICE_PATTERNS = [
        "fuera de la oficina",
        "out of office",
        "vacaciones",
        "de vacaciones",
        "on vacation",
        "ausente",
        "no estaré",
        "no estaré disponible",
        "I will be out",
        "I'm out of office",
        "away from my desk",
        "不在办公室",   # Chino
        "不在辦公室",   # Chino tradicional
        "不在",        # Chino simplificado
    ]

    # Respuestas automáticas de sistemas
    AUTO_REPLY_PATTERNS = [
        "auto-reply",
        "automatic reply",
        "respuesta automática",
        "mensaje automático",
        "generado automáticamente",
        "do not reply",
        "do-not-reply",
        "noreply",
        "no-reply",
        "no reply",
        "mailer-daemon",
        "mail delivery system",
        "entregado automáticamente",
        "automated message",
        "this is an automated",
    ]

    # Notificaciones de entrega / fallo
    BOUNCE_PATTERNS = [
        "undelivered",
        "returned mail",
        "entrega fallida",
        "mensaje no entregado",
        "delivery failure",
        "delivery status",
        "failure notice",
        "non-delivery",
    ]

    # Newsletters y mailing (asuntos comunes)
    NEWSLETTER_PATTERNS = [
        "newsletter",
        "boletín",
        "newsletter",
        "no responda este correo",
        "this email was sent to",
        "you are receiving this because",
        "you have subscribed to",
        "has recibido este email porque",
        "para cancelar la suscripción",
        "unsubscribe",
        "darse de baja",
    ]

    # Remitentes automáticos conocidos
    AUTOMATED_SENDERS = [
        "mailer-daemon@",
        "noreply@",
        "no-reply@",
        "do-not-reply@",
        "notificaciones@",
        "notifications@",
        "noreply",
        "mailer-daemon",
        "postmaster@",
    ]

    def evaluate(self, email_data: EmailParsed) -> "FilterResult":
        """
        Evalúa si un email debe filtrarse o no.

        Pasa por varias pruebas en orden. Si alguna falla,
        el email se marca como irrelevante con el motivo.

        Args:
            email_data: Email ya parseado

        Returns:
            FilterResult con la decisión
        """
        # Si no se pudo parsear, lo filtramos por seguridad
        if email_data is None:
            return FilterResult(False, "Email nulo o no parseable")

        reason = None

        # ── Prueba 1: Remitente automático ──
        reason = self._check_sender(email_data)
        if reason:
            return FilterResult(False, reason)

        # ── Prueba 2: Asunto de fuera de oficina ──
        reason = self._check_out_of_office(email_data)
        if reason:
            return FilterResult(False, reason)

        # ── Prueba 3: Respuesta automática ──
        reason = self._check_auto_reply(email_data)
        if reason:
            return FilterResult(False, reason)

        # ── Prueba 4: Bounce / fallo de entrega ──
        reason = self._check_bounce(email_data)
        if reason:
            return FilterResult(False, reason)

        # ── Prueba 5: Spam / Newsletter ──
        reason = self._check_newsletter(email_data)
        if reason:
            return FilterResult(False, reason)

        # Pasó todas las pruebas → es relevante
        return FilterResult(True, "Email relevante")

    # ──────────────────────────────────────────────
    # PRUEBAS INDIVIDUALES
    # ──────────────────────────────────────────────

    def _check_sender(self, email_data: EmailParsed) -> Optional[str]:
        """¿El remitente es un sistema automático conocido?"""
        sender_lower = email_data.sender_email.lower()

        for pattern in self.AUTOMATED_SENDERS:
            if pattern in sender_lower:
                return f"Remitente automático: {email_data.sender_email}"

        # También el nombre del remitente
        name_lower = email_data.sender_name.lower()
        for pattern in ["mailer", "daemon", "noreply", "notificaciones"]:
            if pattern in name_lower:
                return f"Nombre de remitente automático: {email_data.sender_name}"

        return None

    def _check_out_of_office(self, email_data: EmailParsed) -> Optional[str]:
        """¿El asunto indica fuera de oficina?"""
        subject_lower = email_data.subject.lower()

        for pattern in self.OUT_OF_OFFICE_PATTERNS:
            if pattern in subject_lower:
                return f"Fuera de oficina detectado: '{pattern}' en asunto"

        return None

    def _check_auto_reply(self, email_data: EmailParsed) -> Optional[str]:
        """¿Es una respuesta automática?"""
        subject_lower = email_data.subject.lower()
        body_lower = email_data.body_plain.lower()

        # Revisar asunto
        for pattern in self.AUTO_REPLY_PATTERNS:
            if pattern in subject_lower:
                return f"Auto-respuesta detectada: '{pattern}' en asunto"

        # Revisar cuerpo (primeras líneas)
        body_start = body_lower[:500]
        for pattern in self.AUTO_REPLY_PATTERNS:
            if pattern in body_start:
                return f"Auto-respuesta detectada: '{pattern}' en cuerpo"

        return None

    def _check_bounce(self, email_data: EmailParsed) -> Optional[str]:
        """¿Es una notificación de entrega fallida?"""
        subject_lower = email_data.subject.lower()

        for pattern in self.BOUNCE_PATTERNS:
            if pattern in subject_lower:
                return f"Bounce detectado: '{pattern}' en asunto"

        return None

    def _check_newsletter(self, email_data: EmailParsed) -> Optional[str]:
        """¿Es un newsletter o correo masivo?"""
        subject_lower = email_data.subject.lower()
        body_lower = email_data.body_plain.lower()

        for pattern in self.NEWSLETTER_PATTERNS:
            if pattern in subject_lower:
                return f"Newsletter detectado: '{pattern}' en asunto"

        # Revisar cuerpo para patrones de "baja"/"unsubscribe"
        body_start = body_lower[:300]
        for pattern in self.NEWSLETTER_PATTERNS:
            if pattern in body_start:
                return f"Newsletter detectado: '{pattern}' en cuerpo"

        return None


class FilterResult:
    """
    Resultado de la evaluación del filtro.

    Attributes:
        is_relevant: True si el email debe procesarse
        reason: Motivo por el que se filtró (solo si is_relevant=False)
    """

    def __init__(self, is_relevant: bool, reason: str = ""):
        self.is_relevant = is_relevant
        self.reason = reason

    def __repr__(self):
        if self.is_relevant:
            return "<FilterResult: ✅ Relevante>"
        return f"<FilterResult: ❌ Filtrado — {self.reason}>"
