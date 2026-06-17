"""
IMAP Fetcher — Conexión con Gmail vía IMAP + App Password.

Flujo SIMPLIFICADO (sin lógica de clasificación — ahora en el Orchestrator):
1. Conecta al servidor IMAP (imap.gmail.com:993)
2. Busca correos por fecha (SINCE, últimos 2 días) en INBOX y [Gmail]/All Mail
3. Dedup por message_id antes de procesar
4. Descarga y parsea cada correo
5. Delega el procesamiento al Orchestrator (clasificación multi-agente)
6. Marca como VISTO (en carpeta que corresponda)
7. Mueve a carpeta temática (solo desde INBOX)
"""

import email
import email.message
import email.utils
import logging
import uuid
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Optional

# IMAP SINCE search necesita nombres de mes en INGLÉS independientemente del locale
_IMAP_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

import imaplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.attachment_storage import StoredAttachment
from src.config import get_settings
from src.db.models import Account, Email
from src.db.session import async_session_factory
from src.orchestrator.context import AttachmentContent, EmailData

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

    # Message-ID — some emails arrive without one (batch SMTP, local forwards, etc.)
    # Return None so the DB layer can auto-generate one instead of inserting ""
    # which would violate UniqueConstraint("message_id", "account_id") on duplicates.
    raw_id = msg.get("Message-ID")
    message_id = raw_id.strip().strip("<>") if raw_id else None

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

    # Attachments — extraer contenido
    has_attachments = False
    attachment_list: list[AttachmentContent] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition") is not None:
                has_attachments = True
                filename = part.get_filename()
                if filename:
                    filename = decode_mime_header(filename)
                else:
                    filename = "attachment"
                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)
                if payload:
                    attachment_list.append(AttachmentContent(
                        filename=filename,
                        content_type=content_type,
                        data=payload,
                        size=len(payload),
                    ))

    return {
        "message_id": message_id,
        "subject": subject,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "recipients": [to_email] if to_email else [],
        "body_plain": body_plain,
        "body_html": body_html,
        "has_attachments": has_attachments,
        "attachments_data": attachment_list,
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

    - Conecta vía IMAP, busca correos desde hace 48h (SINCE, no UNSEEN).
    - Gmail a veces marca como VISTO al auto-categorizar, por eso SINCE es más fiable.
    - Deduplica por message_id contra BD para no reprocesar.
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

    # Buscar correos recientes en INBOX + [Gmail]/All Mail.
    # Gmail a veces auto-archiva emails (los mueve de INBOX a All Mail)
    # al marcarlos como VISTO o aplicar categorías automáticas.
    # Buscar SÓLO en INBOX puede perder esos correos.
    try:
        since_date = datetime.now(timezone.utc) - timedelta(hours=48)
        imap_date = f"{since_date.day:02d}-{_IMAP_MONTHS[since_date.month - 1]}-{since_date.year}"
    except Exception as e:
        summary["error"] = f"Error calculating date: {e}"
        imap.logout()
        return summary

    # ── Procesar cada carpeta por separado ──
    # Los ID de mensaje IMAP son específicos de cada carpeta, así que
    # debemos procesar INBOX y All Mail con selects independientes.
    folders_to_search = [settings.imap_folder]
    try:
        imap.select('[Gmail]/All Mail')
        _ = imap.search(None, 'ALL')  # solo verificar que existe
        folders_to_search.append('[Gmail]/All Mail')
    except Exception:
        logger.info("[Gmail]/All Mail no accesible — solo INBOX")
    finally:
        imap.select(settings.imap_folder)

    # Límite de correos por carpeta para no exceder 512MB de RAM en Render
    MAX_FETCH_PER_FOLDER = 20

    close_db = db is None
    session = db or async_session_factory()
    from src.orchestrator.orchestrator import Orchestrator
    orchestrator = Orchestrator()

    moved_count = 0
    folder_map = settings.imap_folder_map or {}

    try:
        for folder in folders_to_search:
            try:
                imap.select(folder)
                logger.info("Buscando en %s desde %s...", folder, imap_date)
            except Exception as e:
                logger.warning("No se pudo seleccionar %s: %s", folder, e)
                continue

            # Buscar correos por fecha
            try:
                _, msg_data = imap.search(None, f'SINCE {imap_date}')
                ids = msg_data[0].split() if msg_data[0] else []
            except Exception as e:
                logger.warning("Error buscando en %s: %s", folder, e)
                continue

            folder_count = len(ids)
            summary["fetched"] += folder_count
            logger.info("%s: %d correos desde %s", folder, folder_count, imap_date)

            if not ids:
                continue

            # Limitar a los N más recientes para no saturar RAM
            ids = ids[-MAX_FETCH_PER_FOLDER:]
            logger.info("Procesando %d correos en %s (limitados a %d)", len(ids), folder, MAX_FETCH_PER_FOLDER)

            # Procesar cada correo
            for msg_id in ids:
                try:
                    _, data = imap.fetch(msg_id, "(RFC822)")
                    raw_bytes = data[0][1]
                    parsed = parse_raw_email(raw_bytes)

                    # Dedup 1: saltar correos reenviados por nuestro pipeline (X-BeExpand)
                    if parsed.get("is_beexpand_forwarded"):
                        logger.info("Saltando email ya procesado (X-BeExpand): %s", parsed.get("subject"))
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                        continue

                    # Dedup 2: saltar si el message_id ya existe en BD
                    if parsed.get("message_id"):
                        existing = await session.execute(
                            select(Email).where(Email.message_id == parsed["message_id"])
                        )
                        if existing.scalar_one_or_none():
                            # Aún así marcar como visto en la carpeta actual
                            try:
                                imap.store(msg_id, "+FLAGS", "\\Seen")
                            except Exception:
                                pass
                            logger.info("Saltando email duplicado (message_id): %s", parsed.get("subject"))
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
                        attachments_data=parsed.get("attachments_data", []),
                        received_at=parsed.get("received_at"),
                    )

                    ctx = await orchestrator.process(email_data, db=session)

                    summary["processed"] += 1
                    summary["results"].append(ctx.summary_dict)

                    # Marcar como visto en la carpeta actual
                    try:
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                    except Exception as e:
                        logger.warning("No se pudo marcar como visto en %s: %s", folder, e)

                    # Mover a carpeta temática (solo si estamos en INBOX)
                    if folder == settings.imap_folder and ctx.final_category and ctx.final_category in folder_map:
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
                        "reenviado" if any(a.success for a in ctx.actions if a.action == "email_forward") else "solo BD",
                    )

                except Exception as e:
                    summary["errors"] += 1
                    logger.error("Error procesando email %s en %s: %s", msg_id, folder, e)
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
                # Volver a INBOX antes de expunge
                imap.select(settings.imap_folder)
                imap.expunge()
                logger.info("EXPUNGE completado en INBOX: %d mensajes", moved_count)
            except Exception as e:
                logger.warning("Error en EXPUNGE: %s", e)
        imap.logout()

    if moved_count > 0:
        summary["moved_to_folders"] = moved_count
        logger.info("Movidos %d emails a carpetas IMAP temáticas", moved_count)

    return summary
