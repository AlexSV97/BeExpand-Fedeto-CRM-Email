"""
IMAP Fetcher — Conexión con Gmail vía IMAP + App Password.

Flujo:
1. Conecta al servidor IMAP (imap.gmail.com:993)
2. Busca correos NO VISTOS (UNSEEN)
3. Descarga y parsea cada correo
4. Crea/actualiza el contacto remitente
5. Guarda el correo en la BD
6. Ejecuta clasificación básica por reglas
7. Marca como VISTO en Gmail
"""

import email
import email.message
import email.utils
import logging
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Account, ClassificationHistory, Contact, Email
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# ── Clasificador por reglas básico (RuleEngine) ──

CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["factura", "invoice", "pago", "payment", "recibo", "receipt"], "cliente"),
    (["presupuesto", "budget", "quote", "cotización"], "lead"),
    (["proveedor", "supplier", "vendor", "orden de compra"], "proveedor"),
    (["soporte", "support", "ayuda", "help", "incidente", "bug"], "cliente"),
    (["reunión", "meeting", "schedule", "agendar"], "cliente"),
]


def classify_by_rules(subject: str, body: str) -> tuple[str, float]:
    """
    Clasifica un correo usando reglas de palabras clave.
    Retorna (categoría, confianza).
    """
    text = f"{subject or ''} {body or ''}".lower()
    for keywords, category in CATEGORY_RULES:
        for kw in keywords:
            if kw in text:
                return category, 0.7
    return "pendiente", 0.3


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


# ── Fetcher principal ──


async def ensure_account(db: AsyncSession) -> Account:
    """Obtiene o crea la cuenta IMAP en BD."""
    settings = get_settings()
    result = await db.execute(
        select(Account).where(Account.email_user == settings.imap_email)
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = Account(
            id=str(uuid.uuid4()),
            name="Gmail POC",
            email_host=settings.imap_server,
            email_port=settings.imap_port,
            email_user=settings.imap_email,
            email_pass=settings.imap_password,
            provider="gmail",
            active=True,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        logger.info("Cuenta IMAP creada: %s", settings.imap_email)
    return account


async def ensure_contact(db: AsyncSession, sender_email: str, sender_name: str) -> Contact:
    """Obtiene o crea un contacto por email."""
    result = await db.execute(
        select(Contact).where(Contact.email == sender_email)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        contact = Contact(
            id=str(uuid.uuid4()),
            name=sender_name or sender_email.split("@")[0],
            email=sender_email,
            category="pendiente",
            source="email",
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)
        logger.info("Contacto creado: %s <%s>", contact.name, contact.email)
    return contact


async def save_email(
    db: AsyncSession,
    account: Account,
    contact: Contact,
    msg_data: dict,
) -> Email:
    """Guarda un correo en la BD si no existe ya por message_id."""
    message_id = msg_data.get("message_id")

    # Evitar duplicados
    if message_id:
        existing = await db.execute(
            select(Email).where(
                Email.message_id == message_id,
                Email.account_id == account.id,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug("Email duplicado (saltando): %s", message_id)
            return None  # type: ignore

    now = datetime.now(timezone.utc)

    # Clasificar
    category, confidence = classify_by_rules(
        msg_data.get("subject", ""),
        msg_data.get("body_plain", ""),
    )

    email = Email(
        id=str(uuid.uuid4()),
        account_id=account.id,
        message_id=message_id,
        subject=msg_data.get("subject", ""),
        body_plain=msg_data.get("body_plain", ""),
        body_html=msg_data.get("body_html", ""),
        sender_email=contact.email,
        sender_name=contact.name,
        recipients=msg_data.get("recipients", []),
        has_attachments=msg_data.get("has_attachments", False),
        received_at=msg_data.get("received_at", now),
        processed_at=now,
        category=category,
        relevance="media",
        status="pendiente",
    )
    db.add(email)
    await db.flush()

    # Guardar history de clasificación
    ch = ClassificationHistory(
        id=str(uuid.uuid4()),
        email_id=email.id,
        category=category,
        confidence=confidence,
        method="rule_engine",
        details={"rules_matched": True},
    )
    db.add(ch)

    # Actualizar contadores del contacto
    contact.email_count = (contact.email_count or 0) + 1
    if contact.first_email_at is None or msg_data.get("received_at", now) < contact.first_email_at:
        contact.first_email_at = msg_data.get("received_at", now)
    if contact.last_email_at is None or msg_data.get("received_at", now) > contact.last_email_at:
        contact.last_email_at = msg_data.get("received_at", now)

    await db.commit()
    logger.info(
        "Email guardado: %s | categoría=%s (%.1f%%)",
        email.subject,
        category,
        confidence * 100,
    )
    return email


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
        "raw_headers": dict(msg.items()),
    }


# ── Sync ──


async def sync_emails(db: Optional[AsyncSession] = None) -> dict:
    """
    Sincroniza correos desde Gmail vía IMAP.
    - Conecta, busca UNSEEN, parsea, clasifica, guarda.
    - Retorna resumen de lo que hizo.
    """
    import imaplib

    settings = get_settings()
    summary = {
        "connected": False,
        "fetched": 0,
        "saved": 0,
        "duplicates": 0,
        "errors": 0,
        "account_email": settings.imap_email,
    }

    if not settings.imap_email or not settings.imap_password:
        summary["error"] = "IMAP no configurado (falta email o password)"
        return summary

    # Conectar IMAP
    try:
        imap = imaplib.IMAP4_SSL(settings.imap_server, settings.imap_port)
        imap.login(settings.imap_email, settings.imap_password)
        imap.select(settings.imap_folder)
        print(f"DEBUG IMAP: connecting to {settings.imap_server}:{settings.imap_port} with email={settings.imap_email} pass len={len(settings.imap_password)} pass=[{settings.imap_password}]")
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

    # Procesar cada correo
    close_db = db is None
    session = db or async_session_factory()

    try:
        account = await ensure_account(session)

        for msg_id in ids:
            try:
                _, data = imap.fetch(msg_id, "(RFC822)")
                raw_bytes = data[0][1]
                parsed = parse_raw_email(raw_bytes)

                # Asegurar contacto
                contact = await ensure_contact(
                    session,
                    parsed["sender_email"],
                    parsed["sender_name"],
                )

                # Guardar email
                saved = await save_email(session, account, contact, parsed)
                if saved:
                    summary["saved"] += 1
                else:
                    summary["duplicates"] += 1

                # Marcar como visto
                imap.store(msg_id, "+FLAGS", "\\Seen")

            except Exception as e:
                summary["errors"] += 1
                logger.error("Error procesando email %s: %s", msg_id, e)
                continue

        # Actualizar last_polled_at
        account.last_polled_at = datetime.now(timezone.utc)
        await session.commit()

    except Exception as e:
        await session.rollback()
        summary["error"] = f"Error en sync: {e}"
        logger.error("Error sync_emails: %s", e)
    finally:
        if close_db:
            await session.close()
        imap.logout()

    return summary
