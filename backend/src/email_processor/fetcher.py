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

import asyncio
import email
import email.message
import email.utils
import json
import logging
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifier.bert_classifier import classify_with_bert
from src.config import get_settings
from src.db.models import Account, ClassificationHistory, Contact, Email
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# ── Clasificador por reglas básico (RuleEngine) ──

# Cada keyword tiene un peso individual (1=genérico, 2=normal, 3=fuerte, 4=muy fuerte).
# El peso refleja qué tan exclusiva es esa palabra de su categoría.
# "gracias" con peso 1 no debería desempatar contra "orden de compra" con peso 4.
KEYWORD_WEIGHTS: list[tuple[str, int, str]] = [
    # ── Cliente: facturación (2) ──
    ("factura", 2, "cliente"),
    ("invoice", 2, "cliente"),
    ("pago", 2, "cliente"),
    ("payment", 2, "cliente"),
    ("recibo", 2, "cliente"),
    ("receipt", 2, "cliente"),
    # ── Cliente: soporte (2-3) ──
    ("soporte", 2, "cliente"),
    ("support", 2, "cliente"),
    ("incidente", 3, "cliente"),
    ("bug", 3, "cliente"),
    ("error", 2, "cliente"),
    ("problema", 2, "cliente"),
    ("urgente", 2, "cliente"),
    ("fallo", 2, "cliente"),
    # ── Cliente: reuniones (1-2) ──
    ("reunión", 2, "cliente"),
    ("reunion", 2, "cliente"),
    ("meeting", 2, "cliente"),
    ("meet", 1, "cliente"),
    ("schedule", 1, "cliente"),
    ("agendar", 1, "cliente"),
    ("follow-up", 2, "cliente"),
    # ── Cliente: genéricos (1 — no desempatan solos) ──
    ("gracias", 1, "cliente"),
    ("thanks", 1, "cliente"),
    ("ayuda", 1, "cliente"),
    ("help", 1, "cliente"),
    # ── Lead: consultas comerciales (2-3) ──
    ("presupuesto", 3, "lead"),
    ("budget", 3, "lead"),
    ("cotización", 3, "lead"),
    ("quot", 2, "lead"),
    ("quote", 2, "lead"),
    ("precio", 2, "lead"),
    ("costo", 2, "lead"),
    ("cost", 2, "lead"),
    ("price", 2, "lead"),
    ("colaboración", 2, "lead"),
    ("partner", 2, "lead"),
    ("collaboration", 2, "lead"),
    ("partnership", 2, "lead"),
    # ── Proveedor: compras y suministros (2-4) ──
    ("orden de compra", 4, "proveedor"),
    ("proveedor", 3, "proveedor"),
    ("supplier", 3, "proveedor"),
    ("vendor", 3, "proveedor"),
    ("pedido", 3, "proveedor"),
    ("order", 2, "proveedor"),
    ("compra", 2, "proveedor"),
    ("purchase", 2, "proveedor"),
    ("materiales", 3, "proveedor"),
    ("suministro", 3, "proveedor"),
]

# Orden de prioridad para desempate.
# En contexto B2B: si hay ambigüedad, proveedor es más específico que lead que cliente.
CATEGORY_PRIORITY: dict[str, int] = {
    "proveedor": 3,
    "lead": 2,
    "cliente": 1,
}


def classify_by_rules(subject: str, body: str) -> tuple[str, float]:
    """
    Clasifica un correo usando palabras clave con pesos individuales.

    - Cada keyword aporta su peso al score de su categoría.
    - Si hay empate, gana la categoría con mayor prioridad (proveedor > lead > cliente).
    - Retorna (categoría, confianza).
    """
    text = f"{subject or ''} {body or ''}".lower()
    scores: dict[str, float] = {}

    for keyword, weight, category in KEYWORD_WEIGHTS:
        if keyword in text:
            scores[category] = scores.get(category, 0) + weight

    if not scores:
        return "pendiente", 0.3

    # Encontrar el score máximo
    max_score = max(scores.values())

    # Todas las categorías que alcanzaron el máximo
    tied = [cat for cat, sc in scores.items() if sc == max_score]

    if len(tied) == 1:
        return tied[0], 0.7

    # Desempate por prioridad de categoría (mayor prioridad gana)
    tied.sort(key=lambda c: CATEGORY_PRIORITY.get(c, 0), reverse=True)
    winner = tied[0]
    logger.info(
        "RuleEngine empate entre %s → desempate gana %s (prioridad %d)",
        tied,
        winner,
        CATEGORY_PRIORITY.get(winner, 0),
    )
    return winner, 0.7


# ── Clasificador por IA (Ollama) ──

CLASSIFY_PROMPT = """Eres un clasificador de correos empresariales.
Analiza el siguiente email y clasifícalo en UNA de estas categorias:
- cliente: el remitente ES un cliente (facturas, pagos, soporte, reuniones)
- lead: es un potencial cliente (presupuestos, cotizaciones, consultas)
- proveedor: el remitente es un proveedor (ordenes de compra, facturas de proveedor)

Responde SOLO con un JSON valido: {{"category": "cliente|lead|proveedor|pendiente", "confidence": 0.0-1.0, "reason": "breve explicacion"}}

Asunto: {subject}
Cuerpo: {body}"""


async def classify_with_ollama(subject: str, body: str) -> tuple[str, float, str]:
    """
    Clasifica un correo usando Ollama (LLM local).
    Retorna (categoría, confianza, razón).
    """
    settings = get_settings()
    prompt = CLASSIFY_PROMPT.format(subject=subject or "", body=body or "")

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,
                    "max_tokens": 128,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()

            # Extraer JSON de la respuesta (puede venir con markdown)
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            category = result.get("category", "pendiente")
            confidence = float(result.get("confidence", 0.5))
            reason = result.get("reason", "")
            return category, confidence, reason

    except Exception as e:
        logger.warning("Ollama classification failed: %s", e)
        return "pendiente", 0.0, f"error: {e}"


# ── Clasificador híbrido ──


async def hybrid_classify(subject: str, body: str) -> tuple[str, float, str, str]:
    """
    Clasificador híbrido de 3 niveles:
    1. RuleEngine  (1ms,  sin red,         confianza >= 70%)
    2. DistilBERT  (50ms, local,            confianza >= 50%)
    3. Ollama/LLM  (1-3s, llama3.2 local,   confianza >= 50%)
    Retorna (categoría, confianza, método, razón).
    """
    # Paso 1: Reglas (instantáneo, sin dependencias)
    category, confidence = classify_by_rules(subject, body)

    if confidence >= 0.7:
        logger.info(
            "RuleEngine acertó: %s (%.0f%%)", category, confidence * 100
        )
        return category, confidence, "rule_engine", "coincidencia por palabra clave"

    # Paso 2: BERT (rápido, modelo local fine-tuned con datos reales + sintéticos)
    # Umbral 80%: el modelo actual está calibrado con datos reales y aumentados.
    # Por debajo de 80%, pasa a Ollama que tiene mejor criterio semántico.
    logger.info("RuleEngine inseguro (%.0f%%) → consultando BERT...", confidence * 100)
    bert_category, bert_confidence = await asyncio.to_thread(
        classify_with_bert, subject, body
    )

    if bert_confidence >= 0.80:
        logger.info(
            "BERT clasificó: %s (%.0f%%)", bert_category, bert_confidence * 100
        )
        return bert_category, bert_confidence, "bert", f"distilBERT: {bert_confidence:.0%}"

    # Paso 3: Ollama (LLM local, último recurso)
    logger.info(
        "BERT inseguro (%.0f%%) → consultando Ollama...", bert_confidence * 100
    )
    ai_category, ai_confidence, ai_reason = await classify_with_ollama(subject, body)

    if ai_confidence >= 0.5:
        return ai_category, ai_confidence, "ollama", ai_reason

    # Si todos fallan, mantener "pendiente"
    return (
        "pendiente",
        max(confidence, bert_confidence, ai_confidence),
        "hybrid_fallback",
        "baja confianza en los 3 niveles",
    )


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

    # Clasificar (híbrido: reglas → IA)
    category, confidence, method, reason = await hybrid_classify(
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
        method=method,
        details={"reason": reason},
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
