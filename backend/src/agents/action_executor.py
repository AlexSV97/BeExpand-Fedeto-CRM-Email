"""
ActionExecutor — ejecuta las acciones post-clasificación del pipeline.

Acciones que ejecuta:
1. Guardar email en BD (con toda la metadata del orquestador)
2. Actualizar/crear contacto
3. Registrar historial de clasificación (votes + decisión final)
4. Notificar por WhatsApp si el correo es urgente
5. Reenviar email a departamentos vía SMTP (si no es nulo)
6. Procesar facturas en adjuntos PDF
7. Registrar resultados de cada acción en el EmailContext

El dashboard consulta la BD directamente, así que al guardar aquí,
el frontend ya ve los datos actualizados.
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.attachment_storage import save_attachment
from src.db.models import ClassificationHistory, Contact, Email, Invoice
from src.email_processor.forwarder import forward_email
from src.domain.ticketing import TicketIngestionInput, TicketPriority, TicketState, Queue
from src.integrations.otrs_znuny.settings import OtrsZnunySettings
from src.orchestrator.context import ActionResult, AttachmentContent, Category, Department, EmailContext, Urgency

logger = logging.getLogger(__name__)

# Patrón para eliminar prefijos de categoría repetidos del asunto
# Ej: "[🏭 PROVEEDOR] [🏭 PROVEEDOR] Factura..." → "Factura..."
_CATEGORY_PREFIX_RE = re.compile(
    r"^(?:\s*\[[^\]]*(?:CLIENTE|LEAD|PROVEEDOR|NULO|SIN\s*CATEGOR)[^\]]*\]\s*)+",
    re.IGNORECASE,
)


def _strip_category_prefixes(subject: str | None) -> str | None:
    """Elimina prefijos de categoría repetidos del asunto (safety net)."""
    if not subject:
        return subject
    cleaned = subject
    while True:
        m = _CATEGORY_PREFIX_RE.match(cleaned)
        if not m:
            break
        cleaned = cleaned[m.end() :].strip()
    return cleaned or subject


class ActionExecutor:
    """Ejecuta las acciones post-clasificación del pipeline."""

    # ── Mapeo de categoría → cola OTRS ──────────────────────────────────
    QUEUE_MAP: dict[str, str] = {
        Category.CLIENTE.value: "Support",
        Category.LEAD.value: "Ventas",
        Category.PROVEEDOR.value: "Proveedores",
    }

    # ── Mapeo de departamento de routing → cola OTRS (fallback Tier 2) ──
    DEPARTMENT_QUEUE_MAP: dict[str, str] = {
        Department.SOPORTE.value: "Support",
        Department.COMERCIAL.value: "Ventas",
        Department.CONTABILIDAD.value: "Contabilidad",
        Department.PROVEEDORES.value: "Proveedores",
        Department.DIRECCION.value: "Direccion",
        Department.OTRO.value: "Support",
    }

    # ── Mapeo de urgencia → prioridad OTRS ──────────────────────────────
    URGENCY_PRIORITY_MAP: dict[str, TicketPriority] = {
        Urgency.ALTA.value: TicketPriority.HIGH,
        Urgency.MEDIA.value: TicketPriority.NORMAL,
        Urgency.BAJA.value: TicketPriority.LOW,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_all(self, ctx: EmailContext) -> list[ActionResult]:
        """
        Ejecuta todas las acciones del pipeline.

        Args:
            ctx: EmailContext completo con categoría, análisis y enrutamiento.

        Returns:
            Lista de resultados de cada acción.
        """
        actions: list[ActionResult] = []

        # 1. Guardar en BD
        db_action = await self._save_to_db(ctx)
        actions.append(db_action)

        # 2. Sincronizar con VTiger CRM (si está configurado)
        crm_action = await self._sync_to_crm(ctx)
        if crm_action:
            actions.append(crm_action)

        # 3. Notificar por WhatsApp si el correo es urgente
        if ctx.final_category and ctx.final_category != Category.NULO.value and ctx.extracted:
            alert_action = await self._notify_whatsapp(ctx)
            actions.append(alert_action)
        else:
            actions.append(ActionResult(
                action="whatsapp_alert",
                success=True,
                detail="Email nulo o sin análisis — no se notifica",
            ))

        # 4. Reenviar email (solo si no es nulo/spam)
        if ctx.final_category != Category.NULO.value and ctx.routing:
            forward_action = await self._forward_email(ctx)
            actions.append(forward_action)
        else:
            actions.append(ActionResult(
                action="email_forward",
                success=True,
                detail="Email nulo o sin ruta — no se reenvía",
            ))

        # 5. Procesar facturas (si el email tiene adjuntos PDF)
        invoice_action = await self._process_invoices(ctx)
        actions.append(invoice_action)

        # 6. Crear ticket en OTRS (si está configurado)
        ticket_action = await self._create_ticket(ctx)
        actions.append(ticket_action)

        ctx.actions = actions
        return actions

    async def _save_to_db(self, ctx: EmailContext) -> ActionResult:
        """Guarda email, contacto y clasificación en BD."""
        try:
            # 1. Asegurar contacto
            contact = await self._ensure_contact(ctx)

            # 2. Guardar email
            email = await self._save_email(ctx, contact)

            # 3. Guardar adjuntos en disco (si hay)
            if ctx.raw.attachments_data:
                await self._save_attachments(ctx, email.id)

            # 4. Guardar historial de clasificación
            await self._save_classification_history(ctx, email.id)

            # 5. Actualizar contadores del contacto
            contact.email_count = (contact.email_count or 0) + 1
            now = ctx.raw.received_at
            if now is None:
                now = datetime.now(timezone.utc)
            elif now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if contact.first_email_at is None or now < contact.first_email_at:
                contact.first_email_at = now
            if contact.last_email_at is None or now > contact.last_email_at:
                contact.last_email_at = now

            await self.db.commit()

            logger.info(
                "BD guardado: %s | categoría=%s (%.0f%%) | método=%s | adjuntos=%d",
                ctx.raw.subject,
                ctx.final_category,
                ctx.final_confidence * 100,
                ctx.resolution_method,
                len(ctx.raw.attachments_data),
            )

            return ActionResult(
                action="db_save",
                success=True,
                detail=f"Email guardado con categoría '{ctx.final_category}'",
            )

        except Exception as e:
            await self.db.rollback()
            logger.error("Error guardando en BD: %s", e)
            return ActionResult(
                action="db_save",
                success=False,
                detail=str(e),
            )

    async def _ensure_contact(self, ctx: EmailContext) -> Contact:
        """Obtiene o crea un contacto por email."""
        sender_email = ctx.raw.sender_email
        sender_name = ctx.raw.sender_name

        result = await self.db.execute(
            select(Contact).where(Contact.email == sender_email)
        )
        contact = result.scalar_one_or_none()

        # Normalizar datetimes al cargar de sqlite (no preserva timezone)
        if contact is not None:
            if contact.first_email_at is not None and contact.first_email_at.tzinfo is None:
                contact.first_email_at = contact.first_email_at.replace(tzinfo=timezone.utc)
            if contact.last_email_at is not None and contact.last_email_at.tzinfo is None:
                contact.last_email_at = contact.last_email_at.replace(tzinfo=timezone.utc)

        if contact is None:
            # Si el analyzer extrajo empresa/cargo, los usamos
            company = ctx.extracted.company if ctx.extracted else None
            position = ctx.extracted.position if ctx.extracted else None

            contact = Contact(
                id=str(uuid.uuid4()),
                name=sender_name or sender_email.split("@")[0],
                email=sender_email,
                company=company,
                position=position,
                category=ctx.final_category or "pendiente",
                source="email",
            )
            self.db.add(contact)
            await self.db.flush()
            logger.info("Contacto creado: %s <%s>", contact.name, contact.email)
        else:
            # Actualizar categoría del contacto si cambió
            if ctx.final_category and ctx.final_category != "nulo":
                contact.category = ctx.final_category
            # Actualizar empresa/cargo si el analyzer los descubrió
            if ctx.extracted:
                if ctx.extracted.company and not contact.company:
                    contact.company = ctx.extracted.company
                if ctx.extracted.position and not contact.position:
                    contact.position = ctx.extracted.position

        return contact

    async def _save_email(self, ctx: EmailContext, contact: Contact) -> Email:
        """Guarda el email en BD."""
        settings = get_settings()

        # Auto-generar message_id si no tiene (ej: correos sin Message-ID header)
        # Esto evita violaciones de UniqueConstraint("message_id", "account_id")
        # cuando múltiples emails llegan sin Message-ID.
        message_id = ctx.raw.message_id
        if not message_id:
            message_id = f"auto-{uuid.uuid4()}"
            logger.debug("Message-ID auto-generado: %s", message_id)
            ctx.raw.message_id = message_id  # ← PROPAGATE back to context

        # Verificar duplicado por message_id + account_id
        if message_id:
            existing = await self.db.execute(
                select(Email).where(
                    Email.message_id == message_id,
                )
            )
            if existing.scalar_one_or_none():
                logger.debug("Email duplicado (saltando): %s", message_id)
                return existing.scalar_one()  # type: ignore

        now = datetime.now(timezone.utc)

        email = Email(
            id=str(uuid.uuid4()),
            account_id=await self._get_or_create_account_id(ctx),
            message_id=message_id,
            subject=_strip_category_prefixes(ctx.raw.subject),
            body_plain=ctx.raw.body_plain,
            body_html=ctx.raw.body_html,
            sender_email=contact.email,
            sender_name=contact.name,
            recipients=ctx.raw.recipients,
            has_attachments=ctx.raw.has_attachments,
            received_at=ctx.raw.received_at,
            processed_at=now,
            category=ctx.final_category or "pendiente",
            relevance=self._determine_relevance(ctx),
            status="pendiente",
            summary=ctx.extracted.summary if ctx.extracted else None,
            extra_data={
                "resolution_method": ctx.resolution_method,
                "confidence": ctx.final_confidence,
                "votes": [
                    {"agent": v.agent_name, "category": v.category, "confidence": v.confidence}
                    for v in ctx.votes
                ],
                "routing": {
                    "departments": ctx.routing.departments if ctx.routing else [],
                    "persons": ctx.routing.persons if ctx.routing else [],
                    "rationale": ctx.routing.rationale if ctx.routing else None,
                },
                "analyzer": {
                    "urgency": ctx.extracted.urgency if ctx.extracted else "media",
                    "action_required": ctx.extracted.action_required if ctx.extracted else None,
                    "tone": ctx.extracted.tone if ctx.extracted else None,
                    "company": ctx.extracted.company if ctx.extracted else None,
                },
                "processing_time_ms": ctx.processing_time_ms,
                "suggested_reply": ctx.suggested_reply or "",
            },
        )
        self.db.add(email)
        await self.db.flush()

        return email

    async def _get_or_create_account_id(self, ctx: EmailContext) -> str:
        """Obtiene o crea el ID de cuenta. Para MVP usamos una cuenta por defecto."""
        from src.db.models import Account

        settings = get_settings()
        result = await self.db.execute(
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
            self.db.add(account)
            await self.db.flush()
        return account.id

    async def _save_classification_history(self, ctx: EmailContext, email_id: str):
        """Guarda cada voto como registro de classification_history."""
        for vote in ctx.votes:
            ch = ClassificationHistory(
                id=str(uuid.uuid4()),
                email_id=email_id,
                category=vote.category,
                confidence=vote.confidence,
                method=vote.agent_name,
                details={
                    "reason": vote.reason,
                    "details": vote.details,
                    "final_category": ctx.final_category,
                    "resolution": ctx.resolution_method,
                },
            )
            self.db.add(ch)

        # También guardar la decisión final como registro adicional
        final_ch = ClassificationHistory(
            id=str(uuid.uuid4()),
            email_id=email_id,
            category=ctx.final_category or "pendiente",
            confidence=ctx.final_confidence,
            method=f"orchestrator_{ctx.resolution_method}",
            details={
                "reason": f"Resolución final: {ctx.resolution_method}",
                "vote_count": len(ctx.votes),
                "resolution": ctx.resolution_method,
                "routing": {
                    "departments": ctx.routing.departments if ctx.routing else [],
                },
            },
        )
        self.db.add(final_ch)

    async def _sync_to_crm(self, ctx: EmailContext) -> ActionResult | None:
        """Sincroniza el contacto con VTiger CRM (si está configurado).

        Crea el contacto en VTiger si no existe, o actualiza su categoría.
        Almacena el crm_id en el contacto local para tracking.
        """
        settings = get_settings()
        if not settings.vtiger_url or not settings.vtiger_token:
            return None  # VTiger no configurado, saltar

        if not ctx.final_category or ctx.final_category == "nulo":
            return ActionResult(
                action="crm_sync",
                success=True,
                detail="Email nulo — no se sincroniza con CRM",
            )

        try:
            from src.integrations.vtiger import VTigerClient, VTigerError

            client = VTigerClient()
            try:
                await client.login()
            except VTigerError as e:
                logger.warning("VTiger no disponible: %s", e)
                return ActionResult(
                    action="crm_sync",
                    success=False,
                    detail=f"VTiger no disponible: {e}",
                )

            # Buscar contacto local
            result = await self.db.execute(
                select(Contact).where(Contact.email == ctx.raw.sender_email)
            )
            contact = result.scalar_one_or_none()
            if not contact:
                return ActionResult(
                    action="crm_sync",
                    success=False,
                    detail="Contacto no encontrado en BD local",
                )

            # Construir datos para VTiger
            company = ctx.extracted.company if ctx.extracted else contact.company
            vtiger_data = {
                "lastname": contact.name.rsplit(" ", 1)[-1] if " " in contact.name else contact.name,
                "firstname": contact.name.rsplit(" ", 1)[0] if " " in contact.name else "",
                "email": contact.email,
                "phone": contact.phone or "",
            }
            # account_id es un campo de referencia que requiere un ID de Account de VTiger (ej: "11x1"),
            # NO un nombre de empresa. Para MVP lo omitimos y guardamos la empresa en description.
            if company:
                vtiger_data["description"] = f"Empresa: {company}"
            if ctx.final_category:
                vtiger_data["cf_categoria"] = ctx.final_category

            # Si ya tiene crm_id, actualizar; si no, crear
            if contact.crm_id:
                await client.update_contact(contact.crm_id, vtiger_data)
                logger.info("Contacto actualizado en VTiger: %s (%s)", contact.crm_id, contact.email)
            else:
                vtiger_id = await client.create_contact(vtiger_data)
                contact.crm_id = vtiger_id
                await self.db.commit()
                logger.info("Contacto creado en VTiger: %s (%s)", vtiger_id, contact.email)

            await client.close()
            return ActionResult(
                action="crm_sync",
                success=True,
                detail=f"Contacto sincronizado con VTiger: {contact.crm_id or 'creado'}",
            )

        except ImportError:
            return ActionResult(
                action="crm_sync",
                success=False,
                detail="Módulo VTiger no disponible",
            )
        except Exception as e:
            logger.error("Error sincronizando con VTiger: %s", e)
            return ActionResult(
                action="crm_sync",
                success=False,
                detail=f"Error CRM: {e}",
            )

    async def _forward_email(self, ctx: EmailContext) -> ActionResult:
        """Reenvía el email a los departamentos destino."""
        if not ctx.routing or not ctx.routing.departments:
            return ActionResult(
                action="email_forward",
                success=True,
                detail="Sin departamentos destino",
            )

        result = await forward_email(
            subject=ctx.raw.subject or "",
            body_plain=ctx.raw.body_plain,
            sender_name=ctx.raw.sender_name,
            sender_email=ctx.raw.sender_email,
            category=ctx.final_category,
            summary=ctx.extracted.summary if ctx.extracted else None,
            departments=ctx.routing.departments,
            original_message_id=ctx.raw.message_id,
        )

        return ActionResult(
            action="email_forward",
            success=result.get("success", False),
            detail=result.get("detail", ""),
        )

    async def _notify_whatsapp(self, ctx: EmailContext) -> ActionResult:
        """Envía alerta a WhatsApp Business si el correo es urgente.

        La decisión de notificar o no depende del WhatsAppNotifier,
        que evalúa el umbral de urgencia configurado (whatsapp_min_urgency).
        """
        from src.notifiers.whatsapp import WhatsAppNotifier

        notifier = WhatsAppNotifier()
        if not notifier.enabled:
            return ActionResult(
                action="whatsapp_alert",
                success=True,
                detail="WhatsApp no configurado — omitido",
            )

        sent = await notifier.send_alert(
            subject=ctx.raw.subject,
            sender_name=ctx.raw.sender_name or "",
            sender_email=ctx.raw.sender_email or "",
            urgency=ctx.extracted.urgency if ctx.extracted else "media",
            category=ctx.final_category or "desconocida",
            summary=ctx.extracted.summary if ctx.extracted else None,
            action_required=ctx.extracted.action_required if ctx.extracted else None,
        )

        return ActionResult(
            action="whatsapp_alert",
            success=sent,
            detail="Alerta enviada a WhatsApp" if sent else "No se envió alerta",
        )

    async def _save_attachments(self, ctx: EmailContext, email_id: str) -> None:
        """Guarda los adjuntos del email en disco y actualiza la referencia en BD.

        Solo se ejecuta si el email tiene adjuntos en attachments_data.
        Los archivos se guardan en: storage/attachments/{email_id}/{filename}
        """
        if not ctx.raw.attachments_data:
            return

        stored_refs = []
        for att in ctx.raw.attachments_data:
            stored = save_attachment(
                email_id=email_id,
                filename=att.filename,
                content_type=att.content_type,
                data=att.data,
            )
            stored_refs.append({
                "filename": stored.filename,
                "content_type": stored.content_type,
                "file_path": stored.file_path,
                "size": stored.size,
                "stored_at": stored.stored_at,
            })

        # Actualizar el campo attachments del email en BD
        from sqlalchemy import select
        from src.db.models import Email as EmailModel

        result = await self.db.execute(
            select(EmailModel).where(EmailModel.id == email_id)
        )
        email = result.scalar_one_or_none()
        if email:
            email.attachments = stored_refs
            await self.db.commit()
            logger.info(
                "%d adjuntos guardados para email %s",
                len(stored_refs), email_id,
            )

    async def _process_invoices(self, ctx: EmailContext) -> ActionResult:
        """Procesa facturas detectadas en adjuntos PDF del email.

        Solo se activa si:
        - El email tiene adjuntos
        - La categoría es 'proveedor' o el Analyzer detectó tipo factura
        - Hay archivos PDF entre los adjuntos

        Extrae los datos estructurados de la factura usando el InvoiceAgent.
        """
        if not ctx.raw.attachments_data:
            return ActionResult(
                action="invoice_process",
                success=True,
                detail="Sin adjuntos — no se procesan facturas",
            )

        # Verificar si hay PDFs entre los adjuntos
        pdf_attachments = [
            a for a in ctx.raw.attachments_data
            if a.content_type == "application/pdf" or a.filename.lower().endswith(".pdf")
        ]

        if not pdf_attachments:
            return ActionResult(
                action="invoice_process",
                success=True,
                detail="Sin archivos PDF entre los adjuntos",
            )

        # Obtener el email_id (último email guardado)
        from sqlalchemy import select
        from src.db.models import Email as EmailModel

        result = await self.db.execute(
            select(EmailModel).where(EmailModel.message_id == ctx.raw.message_id)
            .order_by(EmailModel.created_at.desc())
        )
        email = result.scalar_one_or_none()
        if not email:
            logger.warning("Email no encontrado en BD para procesar facturas")
            return ActionResult(
                action="invoice_process",
                success=False,
                detail="Email no encontrado en BD",
            )

        # Procesar cada PDF con InvoiceAgent
        from src.agents.invoice_agent import InvoiceAgent

        agent = InvoiceAgent()
        invoices_created = 0
        errors = []

        for pdf_att in pdf_attachments:
            try:
                from src.attachment_storage import ATTACHMENTS_DIR

                email_attachments_dir = ATTACHMENTS_DIR / email.id
                if not email_attachments_dir.exists():
                    logger.warning("Directorio de adjuntos no encontrado: %s", email_attachments_dir)
                    continue

                pdf_path = email_attachments_dir / pdf_att.filename
                if not pdf_path.exists():
                    logger.warning("PDF no encontrado en disco: %s", pdf_path)
                    continue

                # Extraer datos de la factura usando el InvoiceAgent
                invoice_data = await agent.extract_invoice(
                    pdf_path=str(pdf_path),
                    filename=pdf_att.filename,
                    email_subject=ctx.raw.subject or "",
                    sender_name=ctx.raw.sender_name or "",
                    sender_email=ctx.raw.sender_email or "",
                )

                if invoice_data:
                    # Guardar registro de factura en BD
                    from datetime import date, datetime

                    # Sanitizar: los date/datetime no son JSON-serializables
                    sanitized_data = {
                        k: v.isoformat() if isinstance(v, (date, datetime)) else v
                        for k, v in invoice_data.items()
                    }

                    invoice_record = Invoice(
                        email_id=email.id,
                        filename=pdf_att.filename,
                        file_path=str(pdf_path),
                        file_size=pdf_att.size,
                        numero=invoice_data.get("numero"),
                        proveedor=invoice_data.get("proveedor"),
                        importe=invoice_data.get("importe"),
                        fecha=invoice_data.get("fecha"),
                        vencimiento=invoice_data.get("vencimiento"),
                        extracted_data=sanitized_data,
                    )
                    self.db.add(invoice_record)
                    invoices_created += 1
                    logger.info(
                        "Factura extraída: %s | %s | %.2f€",
                        invoice_data.get("numero", "?"),
                        invoice_data.get("proveedor", "?"),
                        invoice_data.get("importe", 0),
                    )

            except Exception as e:
                logger.error("Error procesando PDF %s: %s", pdf_att.filename, e)
                errors.append(str(e))

        if invoices_created > 0:
            await self.db.commit()
            return ActionResult(
                action="invoice_process",
                success=True,
                detail=f"{invoices_created} factura(s) extraída(s) de {len(pdf_attachments)} PDF(s)",
            )

        return ActionResult(
            action="invoice_process",
            success=len(errors) == 0,
            detail=f"No se extrajeron facturas ({len(errors)} errores)" if errors else "PDF procesado sin datos de factura",
        )

    def _resolve_queue(self, ctx: EmailContext) -> Queue:
        """Resuelve la cola OTRS aplicando el fallback de 3 niveles.

        Tier 1 — Category match: lookup directo en QUEUE_MAP.
        Tier 2 — Department match: primer departamento de routing que coincida.
        Tier 3 — Default queue: OtrsZnunySettings.default_queue ("Support").
        """
        # Tier 1: categoría conocida
        if ctx.final_category:
            mapped = self.QUEUE_MAP.get(ctx.final_category)
            if mapped:
                return Queue(name=mapped)

        # Tier 2: departamentos de routing
        if ctx.routing and ctx.routing.departments:
            for dept in ctx.routing.departments:
                mapped = self.DEPARTMENT_QUEUE_MAP.get(dept)
                if mapped:
                    return Queue(name=mapped)

        # Tier 3: cola por defecto
        return Queue(name=OtrsZnunySettings().default_queue)

    async def _validate_queue(self, queue: Queue) -> Queue:
        """Valida la cola resuelta contra la tabla ``queues`` (CE-01, REQ-4).

        Si el nombre existe como fila activa en BD, devuelve la cola enriquecida
        con su id/slug/tier/owner. Si no existe (o la BD no es accesible),
        cae a ``OtrsZnunySettings.default_queue`` (fail-open).
        """
        from src.db.models import QueueModel

        try:
            row = (
                await self.db.execute(
                    select(QueueModel).where(
                        QueueModel.name == queue.name,
                        QueueModel.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if row is not None:
                return Queue(
                    id=str(row.id),
                    name=row.name,
                    slug=row.slug,
                    tier=row.tier,
                    owner=row.owner,
                    parent_id=None,
                    is_active=row.is_active,
                    metadata=row.queue_metadata or {},
                )

            default_name = OtrsZnunySettings().default_queue
            if queue.name == default_name:
                return queue
            logger.warning(
                "Cola '%s' no existe en la tabla queues; usando default '%s'",
                queue.name,
                default_name,
            )
            return Queue(name=default_name)
        except Exception:  # noqa: BLE001 — fail-open: nunca bloquear la creación del ticket
            return queue

    def _build_ticket_input(self, ctx: EmailContext) -> TicketIngestionInput:
        """Construye un TicketIngestionInput a partir del EmailContext.

        Aplica los mapeos de cola, prioridad, estado y metadata
        según el diseño en §3.1 de IN-01.
        """
        # Resolver urgencia y prioridad
        urgency = ctx.extracted.urgency if ctx.extracted else "media"
        priority = self.URGENCY_PRIORITY_MAP.get(urgency, TicketPriority.NORMAL)

        # Metadata de clasificación
        metadata: dict = {
            "category": ctx.final_category,
            "confidence": ctx.final_confidence,
            "resolution_method": ctx.resolution_method,
            "urgency": urgency,
            "action_required": ctx.extracted.action_required if ctx.extracted else None,
        }

        return TicketIngestionInput(
            subject=ctx.raw.subject or "",
            body_text=ctx.raw.body_plain or "",
            body_html=ctx.raw.body_html,
            sender_name=ctx.raw.sender_name,
            sender_email=ctx.raw.sender_email,
            recipients=ctx.raw.recipients or [],
            message_id=ctx.raw.message_id,
            received_at=ctx.raw.received_at,
            queue=self._resolve_queue(ctx),
            priority=priority,
            state=TicketState.NEW,
            comment_text=ctx.extracted.summary if ctx.extracted else None,
            comment_visible_to_customer=False,
            metadata=metadata,
        )

    async def _create_ticket(self, ctx: EmailContext) -> ActionResult:
        """Crea un ticket en OTRS/Znuny a partir del email clasificado.

        Guardas:
        - Si OTRS no está configurado → skip con ActionResult(success=True)
        - Si la categoría es nulo/None → skip con ActionResult(success=True)

        Error handling: NUNCA re-lanza excepción. Siempre retorna ActionResult.
        """
        from src.services.ticket_ingestion import TicketIngestionService

        # Guard: OTRS no configurado
        if not OtrsZnunySettings().is_configured:
            logger.info("OTRS no configurado — omitiendo creación de ticket")
            return ActionResult(
                action="otrs_ticket_create",
                success=True,
                detail="OTRS no configurado — omitido",
            )

        # Guard: email nulo
        if ctx.final_category is None or ctx.final_category == Category.NULO.value:
            logger.info("Email nulo — no se crea ticket")
            return ActionResult(
                action="otrs_ticket_create",
                success=True,
                detail="Email nulo — no se crea ticket",
            )

        # ── PRE-CHECK: ¿ya existe ticket OTRS para este email? ──────────────
        message_id = ctx.raw.message_id
        if message_id:
            try:
                result = await self.db.execute(
                    select(Email).where(Email.message_id == message_id)
                )
                email = result.scalar_one_or_none()
                if email and email.otrs_ticket_id:
                    logger.info(
                        "Ticket %s ya existe para email %s",
                        email.otrs_ticket_id, message_id,
                    )
                    return ActionResult(
                        action="otrs_ticket_create",
                        success=True,
                        detail=f"Ticket {email.otrs_ticket_id} ya existe",
                    )
            except Exception:
                logger.warning(
                    "Error en pre-check de duplicado — continuando (fail-open)"
                )

        try:
            input_data = self._build_ticket_input(ctx)
            # CE-01 (REQ-4): validar la cola resuelta contra la tabla queues
            input_data.queue = await self._validate_queue(input_data.queue)
            service = TicketIngestionService()
            try:
                ticket = await service.ingest_email(input_data)
                logger.info(
                    "Ticket creado: %s en cola %s",
                    ticket.id,
                    ticket.queue.name,
                )

                # ── POST-SAVE: persistir otrs_ticket_id en el Email ─────────
                if message_id:
                    try:
                        r2 = await self.db.execute(
                            select(Email).where(Email.message_id == message_id)
                        )
                        email2 = r2.scalar_one_or_none()
                        if email2:
                            email2.otrs_ticket_id = ticket.id
                            email2.otrs_ticket_created_at = datetime.now(timezone.utc)
                            await self.db.commit()
                            logger.debug(
                                "otrs_ticket_id=%s guardado para email %s",
                                ticket.id, message_id,
                            )
                    except Exception:
                        await self.db.rollback()
                        logger.warning(
                            "No se pudo persistir otrs_ticket_id para %s —"
                            " ticket %s ya existe en OTRS (fail-soft)",
                            message_id, ticket.id,
                        )

                return ActionResult(
                    action="otrs_ticket_create",
                    success=True,
                    detail=f"Ticket {ticket.id} creado en cola {ticket.queue.name}",
                )
            finally:
                await service.aclose()
        except Exception as e:
            logger.warning("Error creando ticket OTRS: %s", e)
            return ActionResult(
                action="otrs_ticket_create",
                success=False,
                detail=str(e),
            )

    def _determine_relevance(self, ctx: EmailContext) -> str:
        """Determina la relevancia del email basado en categoría y urgencia."""
        if ctx.final_category == Category.NULO.value:
            return "baja"
        if ctx.final_category == Category.LEAD.value:
            return "alta"
        if ctx.extracted and ctx.extracted.urgency == "alta":
            return "alta"
        return "media"
