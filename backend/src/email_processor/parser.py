"""
Parser de Correos — Extracción de datos estructurados.

¿Qué hace?
Coge un email en bruto (bytes) y lo convierte en un diccionario
con campos útiles: asunto, remitente, cuerpo, adjuntos, etc.

Usa la librería estándar `email` de Python — sin dependencias externas.
"""

import email
import email.utils
import logging
from datetime import datetime
from email.header import decode_header
from email.message import Message
from typing import Optional

logger = logging.getLogger(__name__)


class EmailParsed:
    """
    Representa un email ya procesado y estructurado.

    Es un contenedor de datos (DTO = Data Transfer Object).
    Todos los campos están limpios y listos para guardar en BD.
    """

    def __init__(
        self,
        message_id: str = "",
        subject: str = "",
        body_plain: str = "",
        body_html: str = "",
        sender_email: str = "",
        sender_name: str = "",
        recipients: list = None,
        date: Optional[datetime] = None,
        has_attachments: bool = False,
        attachments: list = None,
        raw_size: int = 0,
    ):
        self.message_id = message_id
        self.subject = subject
        self.body_plain = body_plain
        self.body_html = body_html
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.recipients = recipients or []
        self.date = date
        self.has_attachments = has_attachments
        self.attachments = attachments or []
        self.raw_size = raw_size

    def __repr__(self):
        return (
            f"<Email: {self.subject[:50]} | "
            f"De: {self.sender_email} | "
            f"Adj: {len(self.attachments)}>"
        )


class EmailParser:
    """
    Convierte emails en bruto (bytes) en objetos EmailParsed.

    Uso:
        parser = EmailParser()
        parsed = parser.parse(raw_bytes)
        print(parsed.subject)  # "Pedido #3842"
        print(parsed.sender_email)  # "ana@garcia-sl.com"
    """

    def parse(self, raw_email: bytes) -> Optional[EmailParsed]:
        """
        Procesa un email en bruto y devuelve sus datos estructurados.

        El proceso es como abrir una carta:
        1. Mira el sobre (cabeceras: from, to, subject, date)
        2. Saca la carta (cuerpo: texto plano o HTML)
        3. Revisa si hay fotos adjuntas (attachments)

        Args:
            raw_email: El email tal como lo devuelve IMAP (bytes)

        Returns:
            EmailParsed con los datos extraídos, o None si hay error
        """
        try:
            # ── Paso 1: Convertir bytes a mensaje email ──
            # email.message_from_bytes() entiende el formato RFC822
            # que es el estándar de los emails en internet
            msg = email.message_from_bytes(raw_email)

            # ── Paso 2: Extraer cabeceras ──
            # ⚠️ Python 3.12+: msg.get() puede devolver Header objects.
            #     _decode_header y _parse_address ya manejan ambos tipos.
            message_id = self._decode_header(msg.get("Message-ID", ""))
            subject = self._decode_header(msg.get("Subject", ""))
            sender_email, sender_name = self._parse_address(msg.get("From", ""))
            recipients = self._parse_recipients(msg)
            date = self._parse_date(str(msg.get("Date", "")))

            # ── Paso 3: Extraer cuerpo y adjuntos ──
            body_plain, body_html, attachments = self._extract_content(msg)

            return EmailParsed(
                message_id=message_id,
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                sender_email=sender_email,
                sender_name=sender_name,
                recipients=recipients,
                date=date,
                has_attachments=len(attachments) > 0,
                attachments=attachments,
                raw_size=len(raw_email),
            )

        except Exception as e:
            logger.error(f"❌ Error al parsear email: {e}")
            return None

    # ──────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ──────────────────────────────────────────────

    def _decode_header(self, raw) -> str:
        """
        Decodifica cabeceras que puedan venir codificadas.

        Acepta str O Header objects (Python 3.12+ devuelve Header
        objects para cabeceras con caracteres no-ASCII).

        Ejemplo: "=?UTF-8?B?UGVkaWRvICMzODQy?=" → "Pedido #3842"
        Header con bytes "Ana Garc\\xc3\\xada" → "Ana García"

        Nota: NO usar str(Header) directamente — en Windows con cp1252
        los caracteres fuera de cp1252 se reemplazan por \\ufffd (�).
        Usar decode_header() que trabaja con Header objects nativamente.
        """
        if raw is None:
            return ""

        # ── Obtener decoded_parts según el tipo de entrada ──
        if not isinstance(raw, str):
            # Header object (Python 3.12+) — decode_header trabaja con él
            try:
                decoded_parts = decode_header(raw)
            except Exception:
                return str(raw)
        else:
            if not raw:
                return ""
            try:
                decoded_parts = decode_header(raw)
            except Exception:
                return raw.strip()

        # ── Reconstruir string desde los partes decodificados ──
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                # Python 3.12+: charset 'unknown-8bit' para bytes raw
                if charset == "unknown-8bit":
                    result.append(part.decode("utf-8", errors="replace"))
                elif charset:
                    result.append(part.decode(charset, errors="replace"))
                else:
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result).strip()

    def _parse_address(self, raw) -> tuple:
        """
        Extrae nombre y email de una dirección.

        Acepta str O Header objects (Python 3.12+).

        "Ana García <ana@garcia-sl.com>" → ("ana@garcia-sl.com", "Ana García")
        "remitente@dominio.com" → ("remitente@dominio.com", "")
        """
        # Normalizar: si es Header object (Python 3.12+), convertirlo
        # usando _decode_header en vez de str() para evitar corrupción UTF-8
        raw = self._decode_header(raw)
        if not raw:
            return ("", "")

        try:
            name, addr = email.utils.parseaddr(raw)
            return (addr.lower(), name.strip())
        except Exception:
            return (raw.strip().lower(), "")

    def _parse_recipients(self, msg: Message) -> list:
        """
        Extrae todos los destinatarios del email.

        Busca en las cabeceras:
        - To: destinatarios principales
        - Cc: copia (courtesy copy)
        - Bcc: copia oculta (blind courtesy copy)

        Returns:
            [{email, name, type}]
        """
        recipients = []

        for header in ["To", "Cc", "Bcc"]:
            raw = msg.get(header, "")
            if not raw:
                continue

            # ⚠️ Python 3.12+: msg.get() devuelve Header objects, decodificar
            if not isinstance(raw, str):
                raw = self._decode_header(raw)
            # Un email puede tener múltiples destinatarios separados por coma
            for addr_raw in raw.split(","):
                addr_raw = addr_raw.strip()
                if not addr_raw:
                    continue
                email_addr, name = self._parse_address(addr_raw)
                if email_addr:
                    recipients.append({
                        "email": email_addr,
                        "name": name,
                        "type": header.lower(),
                    })

        return recipients

    def _parse_date(self, raw: str) -> Optional[datetime]:
        """
        Convierte la fecha del email a datetime de Python.

        Los emails usan formato RFC2822:
        "Mon, 11 May 2026 09:34:21 +0200"
        """
        if not raw:
            return None

        try:
            parsed = email.utils.parsedate_to_datetime(raw)
            return parsed
        except Exception:
            logger.warning(f"⚠️ No se pudo parsear fecha: {raw[:50]}")
            return None

    def _extract_content(self, msg: Message) -> tuple:
        """
        Extrae el cuerpo del email y los adjuntos.

        Un email puede tener varias partes (multipart):
        - text/plain: el cuerpo en texto plano
        - text/html: el cuerpo con formato HTML
        - application/pdf: un adjunto (PDF, DOCX, etc.)
        - image/jpg: una imagen adjunta

        Returns:
            (body_plain, body_html, [attachments])
        """
        body_plain = ""
        body_html = ""
        attachments = []

        if not msg.is_multipart():
            # Email simple: solo texto plano
            content_type = msg.get_content_type()
            payload = self._decode_payload(msg)

            if content_type == "text/plain":
                body_plain = payload
            elif content_type == "text/html":
                body_html = payload
            else:
                body_plain = payload or ""
        else:
            # Email con múltiples partes (lo más común)
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # ── ¿Es un adjunto? ──
                # Si tiene Content-Disposition: attachment, es adjunto
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        attachments.append({
                            "filename": filename,
                            "content_type": content_type,
                            "size": len(part.get_payload(decode=True) or b""),
                        })
                    continue

                # ── ¿Es el cuerpo? ──
                # Si no es adjunto, es parte del cuerpo del email
                payload = self._decode_payload(part)

                if content_type == "text/plain" and not body_plain:
                    body_plain = payload
                elif content_type == "text/html" and not body_html:
                    body_html = payload

        return (body_plain, body_html, attachments)

    def _decode_payload(self, part: Message) -> str:
        """
        Decodifica el contenido de una parte del email.

        Los emails pueden venir codificados en:
        - base64 (común en adjuntos)
        - quoted-printable (común en texto)
        - 7bit / 8bit (sin codificar)

        Y en diferentes juegos de caracteres:
        - UTF-8
        - ISO-8859-1 (Latín)
        - Windows-1252
        etc.
        """
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""

            charset = part.get_content_charset() or "utf-8"

            try:
                return payload.decode(charset, errors="replace")
            except (LookupError, ValueError):
                # Si el charset no es válido, probar UTF-8
                return payload.decode("utf-8", errors="replace")

        except Exception as e:
            logger.warning(f"⚠️ Error al decodificar payload: {e}")
            return ""
