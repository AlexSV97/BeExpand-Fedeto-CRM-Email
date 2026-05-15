"""
SMTP Forwarder — reenvía emails a los departamentos correspondientes.

Usa las mismas credenciales Gmail que la conexión IMAP.
Los departamentos se mapean a alias "+" de Gmail para pruebas.

Ejemplo:
  Departamento "contabilidad" → beexpandcrmpoc+contabilidad@gmail.com
  Departamento "soporte"     → beexpandcrmpoc+soporte@gmail.com
"""

import email.message
import email.utils
import logging
import smtplib
import time
from datetime import datetime, timezone

from src.config import get_settings

logger = logging.getLogger(__name__)

# Mapeo de departamentos a alias de email (Gmail + addressing)
# Todas las direcciones +alias entregan en la misma bandeja principal
DEPARTMENT_EMAILS: dict[str, str] = {
    "contabilidad": "beexpandcrmpoc+contabilidad@gmail.com",
    "soporte": "beexpandcrmpoc+soporte@gmail.com",
    "comercial": "beexpandcrmpoc+comercial@gmail.com",
    "proveedores": "beexpandcrmpoc+proveedores@gmail.com",
    "direccion": "beexpandcrmpoc+direccion@gmail.com",
    "otro": "beexpandcrmpoc+otro@gmail.com",
}

CATEGORY_LABELS: dict[str, str] = {
    "cliente": "👤 CLIENTE",
    "lead": "⭐ LEAD",
    "proveedor": "🏭 PROVEEDOR",
    "nulo": "🚫 NULO",
}


def _build_forward_email(
    subject: str,
    body_plain: str | None,
    sender_name: str,
    sender_email: str,
    category: str | None,
    summary: str | None,
    departments: list[str],
    original_message_id: str | None,
) -> str:
    """
    Construye el email a reenviar con metadatos del sistema.

    Returns:
        El email como string (formato RFC 822).
    """
    category_label = CATEGORY_LABELS.get(category or "", "📋 SIN CATEGORÍA")

    # Prefijo en el asunto para identificar el origen
    new_subject = f"[{category_label}] {subject or '(sin asunto)'}"

    # Cuerpo del email reenviado
    forward_body = f"""╔══════════════════════════════════════════╗
║   BEEXPAND CRM — EMAIL CLASIFICADO     ║
╠══════════════════════════════════════════╣
║ Categoría: {category_label:<29} ║
║ Confianza: {category or 'N/A':<31} ║
║ Destino:   {', '.join(departments):<29} ║
║ Fecha:     {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M'):<21} ║
╚══════════════════════════════════════════╝

{'─' * 50}
RESUMEN DEL ANÁLISIS
{'─' * 50}
{summary or 'No se pudo generar resumen automático.'}

{'─' * 50}
CORREO ORIGINAL
{'─' * 50}
De: {sender_name} <{sender_email}>
Asunto: {subject or '(sin asunto)'}

{body_plain or '(sin contenido)'}
"""

    # Construir el mensaje RFC822
    msg = email.message.EmailMessage()
    msg["Subject"] = new_subject
    msg["From"] = f"BeExpand CRM <{sender_email}>"
    msg["To"] = ", ".join(
        DEPARTMENT_EMAILS.get(d, f"beexpandcrmpoc+{d}@gmail.com")
        for d in departments
    )
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain="beexpand.crm")
    msg["X-BeExpand-Category"] = category or "sin-categoria"
    msg["X-BeExpand-Departments"] = ",".join(departments)
    if original_message_id:
        msg["X-BeExpand-Original-Message-ID"] = original_message_id

    msg.set_content(forward_body)

    return msg.as_string()


async def forward_email(
    subject: str,
    body_plain: str | None,
    sender_name: str,
    sender_email: str,
    category: str | None,
    summary: str | None,
    departments: list[str],
    original_message_id: str | None = None,
) -> dict:
    """
    Reenvía el email a los departamentos destino vía SMTP.

    Returns:
        dict con "success": bool y "detail": str
    """
    settings = get_settings()

    if not departments or departments == ["otro"]:
        return {
            "success": False,
            "detail": "Sin departamento destino definido, no se reenvía",
        }

    if not settings.imap_email or not settings.imap_password:
        return {
            "success": False,
            "detail": "SMTP no configurado (falta email o password)",
        }

    # Construir email
    email_content = _build_forward_email(
        subject=subject or "",
        body_plain=body_plain,
        sender_name=sender_name,
        sender_email=sender_email,
        category=category,
        summary=summary,
        departments=departments,
        original_message_id=original_message_id,
    )

    # Enviar vía SMTP
    try:
        loop = None
        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        def _send():
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(settings.imap_email, settings.imap_password)
                to_addrs = [
                    DEPARTMENT_EMAILS.get(d, f"beexpandcrmpoc+{d}@gmail.com")
                    for d in departments
                ]
                server.sendmail(settings.imap_email, to_addrs, email_content)
            return len(to_addrs)

        if loop:
            sent_count = await loop.run_in_executor(None, _send)
        else:
            sent_count = _send()

        logger.info(
            "Email reenviado a %d departamento(s): %s",
            sent_count,
            ", ".join(departments),
        )
        return {
            "success": True,
            "detail": f"Reenviado a {sent_count} departamento(s): {', '.join(departments)}",
        }

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth error — revisar credenciales Gmail/App Password")
        return {"success": False, "detail": "Error de autenticación SMTP"}
    except smtplib.SMTPException as e:
        logger.error("SMTP error: %s", e)
        return {"success": False, "detail": f"Error SMTP: {e}"}
    except Exception as e:
        logger.error("Error reenviando email: %s", e)
        return {"success": False, "detail": f"Error inesperado: {e}"}
