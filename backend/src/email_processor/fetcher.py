"""
IMAP Fetcher — Conexión con Gmail vía IMAP + App Password.

Flujo SIMPLIFICADO (sin lógica de clasificación — ahora en el Orchestrator):
1. Conecta al servidor IMAP (imap.gmail.com:993)
2. Busca correos NO VISTOS (UNSEEN)
3. Descarga y parsea cada correo
4. Delega el procesamiento al Orchestrator (clasificación multi-agente)
5. Marca como VISTO en Gmail
"""

import email
import email.message
import email.utils
import logging
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

import imaplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Account
from src.db.session import async_session_factory
from src.orchestrator.context import EmailData

logger = logging.getLogger(__name__)


# ── Parseo de cabeceras de email ──


def decode_mime_header(header_value: bytes | str | None) -> str:
    """Decodifica cabeceras MIME a texto plano."""
    if not header_value:
        return ""
    if isinstance(header_value, bytes):
        header_value = header_value.decode("utf-8", errors="replace")
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def parse_email_address(raw: str) -> tuple[str, str]:
    """Extrae nombre y email de una cabecera 'From'/'To'."""
    import re
    match = re.search(r'[^<]*<([^>]+)>', raw)
    if match:
        name = raw[:match.start()].strip().strip('"')
        email_addr = match.group(1).strip()
        return name, email_addr.lower()
    return "", raw.strip().lower()


def get_email_body(msg: email.message.Message) -> tuple[str, str]:
    """Extrae body plano y HTML de un mensaje de email."""
    plain_text = ""
    html_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                try:
                    plain_text = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    plain_text = str(part.get_payload(decode=True))
            elif ctype == "text/html":
                charset = part.get_content_charset() or "utf-8"
                try:
                    html_text = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    html_text = str(part.get_payload(decode=True))
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            charset = msg.get_content_charset() or "utf-8"
            try:
                plain_text = msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                plain_text = str(msg.get_payload(decode=True))
        elif ctype == "text/html":
            charset = msg.get_content_charset() or "utf-8"
            try:
                html_text = msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                html_text = str(msg.get_payload(decode=True))
    return plain_text, html_text


def parse_raw_email(raw_bytes: bytes) -> dict:
    """Parsea un email raw desde IMAP a dict."""
    msg = email.message_from_bytes(raw_bytes)

    # Cabeceras
    subject = decode_mime_header(msg["Subject"])
    from_raw = decode_mime_header(msg["From"])
    sender_name, sender_email = parse_email_address(from_raw)
    to_raw = decode_mime_header(msg["To"])
    _, to_email = parse_email_address(to_raw)

    # Message-ID
    message_id = msg.get("Message-ID", "").strip().strip("<>")

    # Fecha
    date_str = msg.get("Date")
    received_at = None
    if date_str:
        try:
            received_at = email.utils.parsedate_to_datetime(date_str)
            if received_at is not None and received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
        except Exception:
            received_at = datetime.now(timezone.utc)

    # Body
    body_plain, body_html = get_email_body(msg)

    # Attachments
    has_attachments = False
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition") is not None:
                has_attachments = True
                break

    return {
        "message_id": message_id,
        "subject": subject,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "recipients": [to_email] if to_email else [],
        "body_plain": body_plain,
        "body_html": body_html,
        "has_attachments": has_attachments,
        "received_at": received_at,
        "is_beexpand_forwarded": bool(msg.get("X-BeExpand-Category")),
    }


# ── Sync con Orchestrator ──


def _ensure_imap_folder(imap, folder_name: str) -> bool:
    """
    Crea una carpeta IMAP si no existe.
    Gmail no distingue entre mayúsculas/minúsculas en nombres de carpeta.
    """
    try:
        imap.create(folder_name)
        logger.info("Carpeta IMAP creada: %s", folder_name)
        return True
    except imaplib.IMAP4.error:
        # La carpeta ya existe — es esperado
        return True
    except Exception as e:
        logger.warning("No se pudo crear carpeta IMAP '%s': %s", folder_name, e)
        return False


def _move_to_imap_folder(imap, msg_id: bytes, folder_name: str) -> bool:
    """
    Mueve un email a otra carpeta IMAP: copia + marca como borrado en origen.
    
    El borrado físico (EXPUNGE) se hace al final del ciclo de sync
    para no alterar los IDs de mensaje durante la iteración.
    """
    try:
        result = imap.copy(msg_id, folder_name)
        if result[0] == "OK":
            imap.store(msg_id, "+FLAGS", "\\Deleted")
            return True
        logger.warning("Copy a %s falló: %s", folder_name, result)
        return False
    except Exception as e:
        logger.error("Error moviendo email %s a %s: %s", msg_id, folder_name, e)
        return False


async def sync_emails(db: Optional[AsyncSession] = None) -> dict:
    """
    Sincroniza correos desde Gmail vía IMAP y los procesa con el Orchestrator.

    - Conecta vía IMAP, busca UNSEEN, parsea cada correo.
    - Delega cada email al Orchestrator (analyzer → classifier → router → executor).
    - Marca como VISTO en Gmail tras procesar.

    Returns:
        Dict con resumen de la operación.
    """
    settings = get_settings()
    summary = {
        "connected": False,
        "fetched": 0,
        "processed": 0,
        "errors": 0,
        "account_email": settings.imap_email,
        "results": [],
    }

    if not settings.imap_email or not settings.imap_password:
        summary["error"] = "IMAP no configurado (falta email o password)"
        return summary

    # Conectar IMAP
    try:
        imap = imaplib.IMAP4_SSL(settings.imap_server, settings.imap_port)
        imap.login(settings.imap_email, settings.imap_password)
        imap.select(settings.imap_folder)
        summary["connected"] = True
        logger.info("Conectado a IMAP: %s", settings.imap_email)
    except Exception as e:
        summary["error"] = f"Error conectando IMAP: {e}"
        logger.error("Error IMAP connect: %s", e)
        return summary

    # Buscar no leídos
    try:
        _, message_ids = imap.search(None, "UNSEEN")
        ids = message_ids[0].split() if message_ids[0] else []
        summary["fetched"] = len(ids)
        logger.info("Correos UNSEEN encontrados: %d", len(ids))
    except Exception as e:
        summary["error"] = f"Error searching IMAP: {e}"
        imap.logout()
        return summary

    if not ids:
        imap.logout()
        return summary

    # Procesar cada correo con el Orchestrator
    close_db = db is None
    session = db or async_session_factory()
    from src.orchestrator.orchestrator import Orchestrator
    orchestrator = Orchestrator()

    moved_count = 0
    folder_map = settings.imap_folder_map or {}

    try:
        for msg_id in ids:
            try:
                _, data = imap.fetch(msg_id, "(RFC822)")
                raw_bytes = data[0][1]
                parsed = parse_raw_email(raw_bytes)

                # Saltar correos que ya pasaron por el pipeline (el forwarder
                # añade cabeceras X-BeExpand-* al reenviar)
                if parsed.get("is_beexpand_forwarded"):
                    logger.info("Saltando email ya procesado (X-BeExpand): %s", parsed.get("subject"))
                    imap.store(msg_id, "+FLAGS", "\\Seen")
                    continue

                # Construir EmailData y procesar con Orchestrator
                email_data = EmailData(
                    message_id=parsed.get("message_id"),
                    subject=parsed.get("subject"),
                    body_plain=parsed.get("body_plain"),
                    body_html=parsed.get("body_html"),
                    sender_name=parsed.get("sender_name", ""),
                    sender_email=parsed.get("sender_email", ""),
                    recipients=parsed.get("recipients", []),
                    has_attachments=parsed.get("has_attachments", False),
                    received_at=parsed.get("received_at"),
                )

                ctx = await orchestrator.process(email_data, db=session)

                summary["processed"] += 1
                summary["results"].append(ctx.summary_dict)

                # Marcar como visto
                imap.store(msg_id, "+FLAGS", "\\Seen")

                # Mover a carpeta temática según categoría
                if ctx.final_category and ctx.final_category in folder_map:
                    target = folder_map[ctx.final_category]
                    _ensure_imap_folder(imap, target)
                    if _move_to_imap_folder(imap, msg_id, target):
                        moved_count += 1
                        logger.debug("Movido %s → %s", parsed.get("subject"), target)

                logger.info(
                    "Procesado: %s → %s (%.0f%%) | ruta: %s | %s",
                    parsed.get("subject"),
                    ctx.final_category,
                    ctx.final_confidence * 100,
                    ", ".join(ctx.routing.departments) if ctx.routing else "n/a",
                    "✅ reenviado" if any(a.success for a in ctx.actions if a.action == "email_forward") else "📥 solo BD",
                )

            except Exception as e:
                summary["errors"] += 1
                logger.error("Error procesando email %s: %s", msg_id, e)
                continue

        # Actualizar last_polled_at en la cuenta por defecto
        try:
            account_result = await session.execute(
                select(Account).where(Account.email_user == settings.imap_email)
            )
            account = account_result.scalar_one_or_none()
            if account:
                account.last_polled_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception:
            await session.rollback()

    except Exception as e:
        await session.rollback()
        summary["error"] = f"Error en sync: {e}"
        logger.error("Error sync_emails: %s", e)
    finally:
        if close_db:
            await session.close()
        if moved_count > 0:
            try:
                imap.expunge()
                logger.info("Expunged %d mensajes marcados como borrados", moved_count)
            except Exception as e:
                logger.warning("Error en EXPUNGE: %s", e)
        imap.logout()

    if moved_count > 0:
        summary["moved_to_folders"] = moved_count
        logger.info("Movidos %d emails a carpetas IMAP temáticas", moved_count)

    return summary
