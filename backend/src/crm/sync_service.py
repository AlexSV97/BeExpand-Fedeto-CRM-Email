"""
CrmSyncService — Orquesta la sincronización entre nuestra DB y VTiger.

¿Qué hace?
  1. Cuando un email se clasifica como Cliente/Lead/Proveedor,
     el ClassifierService llama a este servicio.
  2. El servicio busca si el contacto ya existe en VTiger.
  3. Si no existe → lo crea. Si existe → lo actualiza.
  4. Si la clasificación es "lead" → además crea una oportunidad.
  5. Todo queda registrado en SyncLogEntry para auditoría.

Si VTiger falla, el servicio captura el error y sigue —
el pipeline de email NO se rompe.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.crm.vtiger_client import VtigerClient, VtigerAuthError, VtigerClientError
from src.db.models import Email, SyncLogEntry, SyncStatus
from src.email_processor.parser import EmailParsed
from src.email_processor.classifier.interfaces import ClassificationResult

logger = logging.getLogger(__name__)


class CrmSyncService:
    """Sincroniza contactos clasificados con VTiger CRM.

    Cada email clasificado como Cliente/Lead/Proveedor dispara:
      1. Upsert del contacto en VTiger (crear si no existe, actualizar si existe)
      2. Si es Lead → crear oportunidad en VTiger
      3. Registrar resultado en SyncLogEntry

    Si VTiger no está disponible, se captura el error, se loguea,
    y el pipeline continúa — el email ya quedó clasificado en nuestra DB.
    """

    def __init__(
        self,
        vtiger_client: VtigerClient,
        db_session: AsyncSession,
    ):
        """
        Args:
            vtiger_client: Cliente ya configurado para hablar con VTiger.
            db_session: Sesión de base de datos para guardar logs de sync.
        """
        self._vtiger = vtiger_client
        self._db = db_session

    async def sync_contact(
        self,
        email_data: EmailParsed,
        classification: ClassificationResult,
        email_record_id: str,
    ) -> dict:
        """Sincroniza un contacto clasificado con VTiger.

        Este es el método principal. Se llama después de clasificar un email.

        Args:
            email_data: El email parseado (de ahí sacamos nombre, email, etc.).
            classification: Resultado de la clasificación (categoría, confianza).
            email_record_id: ID del registro Email en nuestra DB (para el log).

        Returns:
            Dict con:
                - "success": bool
                - "contact_id": str o None
                - "opportunity_id": str o None
                - "action": "created" | "updated" | "skipped" | "error"
        """
        # Solo sincronizamos si es una categoría que nos interesa
        if classification.category not in ("cliente", "lead", "proveedor"):
            return {
                "success": True,
                "contact_id": None,
                "opportunity_id": None,
                "action": "skipped",
                "reason": f"Categoría '{classification.category}' no requiere sync",
            }

        try:
            # ── Paso 1: Asegurar sesión en VTiger ──
            if not self._vtiger._session_id:
                await self._vtiger.login()

            # ── Paso 2: Buscar contacto por email ──
            contact_id = await self._upsert_contact(email_data)

            # ── Paso 3: Si es Lead, crear oportunidad ──
            opportunity_id = None
            if classification.category == "lead" and contact_id:
                opportunity_id = await self._create_lead_opportunity(
                    contact_id, email_data, classification
                )

            # ── Paso 4: Registrar en SyncLogEntry ──
            action = "created" if contact_id and not self._contact_exists else "updated"
            await self._log_sync(
                email_record_id=email_record_id,
                status=SyncStatus.COMPLETED,
                details={
                    "action": action,
                    "contact_id": contact_id,
                    "opportunity_id": opportunity_id,
                    "category": classification.category,
                    "confidence": classification.confidence,
                },
            )

            logger.info(
                "Contacto sincronizado: email=%s, category=%s, contact=%s, opp=%s",
                email_data.sender_email,
                classification.category,
                contact_id,
                opportunity_id or "N/A",
            )

            return {
                "success": True,
                "contact_id": contact_id,
                "opportunity_id": opportunity_id,
                "action": action,
            }

        except VtigerAuthError as e:
            # Error de autenticación — no vamos a poder hacer nada
            # hasta que alguien actualice las credenciales
            logger.error("Error de autenticación VTiger: %s", e)
            await self._log_sync(
                email_record_id=email_record_id,
                status=SyncStatus.FAILED,
                details={"error": str(e), "category": classification.category},
            )
            return {"success": False, "contact_id": None, "opportunity_id": None, "action": "error"}

        except (VtigerClientError, httpx.TimeoutException) as e:
            # Error de conexión — VTiger puede estar caído.
            # El email ya está clasificado en nuestra DB,
            # se reintentará en el próximo ciclo de sync.
            logger.warning("VTiger no disponible (mode degradado): %s", e)
            await self._log_sync(
                email_record_id=email_record_id,
                status=SyncStatus.FAILED,
                details={"error": str(e), "category": classification.category},
            )
            return {"success": False, "contact_id": None, "opportunity_id": None, "action": "error"}

    async def _upsert_contact(self, email_data: EmailParsed) -> Optional[str]:
        """Crea o actualiza un contacto en VTiger según su email.

        Estrategia:
            1. Buscar contacto por email en VTiger
            2. Si existe → actualizar sus datos
            3. Si no existe → crear nuevo

        Returns:
            ID del contacto en VTiger, o None si falla.
        """
        # Buscar si ya existe
        existing = await self._vtiger.get_contact_by_email(email_data.sender_email)

        contact_data = {
            "email": email_data.sender_email,
            "lastname": email_data.sender_name or email_data.sender_email.split("@")[0],
            "assigned_user_id": "19x1",  # Usuario por defecto en VTiger
        }

        if existing:
            # Ya existe → actualizar
            self._contact_exists = True
            contact_id = existing.get("id")
            if contact_id:
                await self._vtiger.update_contact(contact_id, contact_data)
                return contact_id
            return None

        # No existe → crear
        self._contact_exists = False
        return await self._vtiger.create_contact(contact_data)

    async def _create_lead_opportunity(
        self,
        contact_id: str,
        email_data: EmailParsed,
        classification: ClassificationResult,
    ) -> Optional[str]:
        """Crea una oportunidad de venta en VTiger para un Lead.

        Args:
            contact_id: ID del contacto en VTiger.
            email_data: Email parseado (asunto → nombre de oportunidad).
            classification: Resultado de clasificación (para la confianza).

        Returns:
            ID de la oportunidad creada, o None si falla.
        """
        potential_data = {
            "potentialname": f"Lead: {email_data.subject[:100]}" if email_data.subject
                            else f"Lead desde email: {email_data.sender_email}",
            "related_to": contact_id,
            "sales_stage": "Nueva",  # Etapa inicial — después se mueve manualmente
            "closingdate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "description": (
                f"Lead generado automáticamente desde email.\n"
                f"Confianza: {classification.confidence}\n"
                f"Asunto: {email_data.subject}\n"
                f"Remitente: {email_data.sender_name} <{email_data.sender_email}>"
            ),
        }

        return await self._vtiger.create_opportunity(potential_data)

    async def _log_sync(
        self,
        email_record_id: str,
        status: SyncStatus,
        details: dict,
    ):
        """Registra el resultado de la sincronización en la DB.

        Args:
            email_record_id: ID del email en nuestra DB.
            status: SyncStatus (COMPLETED, FAILED, PENDING).
            details: Dict con información adicional.
        """
        log_entry = SyncLogEntry(
            email_id=email_record_id,
            status=status,
            details=details,
        )
        self._db.add(log_entry)
        await self._db.commit()
