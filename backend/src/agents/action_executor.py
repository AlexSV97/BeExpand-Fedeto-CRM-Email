"""
ActionExecutor — ejecuta las acciones post-clasificación del pipeline.

Acciones que ejecuta:
1. Guardar email en BD (con toda la metadata del orquestador)
2. Actualizar/crear contacto
3. Registrar historial de clasificación (votes + decisión final)
4. Reenviar email a departamentos vía SMTP (si no es nulo)
5. Registrar resultados de cada acción en el EmailContext

El dashboard consulta la BD directamente, así que al guardar aquí,
el frontend ya ve los datos actualizados.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import ClassificationHistory, Contact, Email
from src.email_processor.forwarder import forward_email
from src.orchestrator.context import ActionResult, Category, EmailContext

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Ejecuta las acciones post-clasificación del pipeline."""

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

        # 2. Reenviar email (solo si no es nulo/spam)
        if ctx.final_category != Category.NULO.value and ctx.routing:
            forward_action = await self._forward_email(ctx)
            actions.append(forward_action)
        else:
            actions.append(ActionResult(
                action="email_forward",
                success=True,
                detail="Email nulo o sin ruta — no se reenvía",
            ))

        ctx.actions = actions
        return actions

    async def _save_to_db(self, ctx: EmailContext) -> ActionResult:
        """Guarda email, contacto y clasificación en BD."""
        try:
            # 1. Asegurar contacto
            contact = await self._ensure_contact(ctx)

            # 2. Guardar email
            email = await self._save_email(ctx, contact)

            # 3. Guardar historial de clasificación
            await self._save_classification_history(ctx, email.id)

            # 4. Actualizar contadores del contacto
            contact.email_count = (contact.email_count or 0) + 1
            now = ctx.raw.received_at or datetime.now(timezone.utc)
            if contact.first_email_at is None or now < contact.first_email_at:
                contact.first_email_at = now
            if contact.last_email_at is None or now > contact.last_email_at:
                contact.last_email_at = now

            await self.db.commit()

            logger.info(
                "BD guardado: %s | categoría=%s (%.0f%%) | método=%s",
                ctx.raw.subject,
                ctx.final_category,
                ctx.final_confidence * 100,
                ctx.resolution_method,
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

        # Verificar duplicado por message_id + account_id
        if ctx.raw.message_id:
            existing = await self.db.execute(
                select(Email).where(
                    Email.message_id == ctx.raw.message_id,
                )
            )
            if existing.scalar_one_or_none():
                logger.debug("Email duplicado (saltando): %s", ctx.raw.message_id)
                return existing.scalar_one()  # type: ignore

        now = datetime.now(timezone.utc)

        email = Email(
            id=str(uuid.uuid4()),
            account_id=await self._get_or_create_account_id(ctx),
            message_id=ctx.raw.message_id,
            subject=ctx.raw.subject,
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

    def _determine_relevance(self, ctx: EmailContext) -> str:
        """Determina la relevancia del email basado en categoría y urgencia."""
        if ctx.final_category == Category.NULO.value:
            return "baja"
        if ctx.final_category == Category.LEAD.value:
            return "alta"
        if ctx.extracted and ctx.extracted.urgency == "alta":
            return "alta"
        return "media"
