"""
Router de sincronización con VTiger CRM.

POST /sync — sincronización manual de contactos pendientes con VTiger.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Contact, User
from src.db.session import get_db

from src.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crm"])


class SyncResult(BaseModel):
    """Resultado de un elemento sincronizado."""
    email: str
    name: str
    crm_id: str | None
    action: str  # created | updated | skipped | error
    detail: str | None = None


class SyncResponse(BaseModel):
    """Resultado completo de la sincronización."""
    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    results: list[SyncResult]
    connected: bool
    detail: str | None = None


@router.post("/sync", response_model=SyncResponse)
async def sync_contacts_to_crm(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sincroniza todos los contactos de la BD local con VTiger CRM.

    Para cada contacto:
    - Si no tiene crm_id → se crea en VTiger
    - Si tiene crm_id → se actualiza en VTiger

    Solo sincroniza contactos con categorías no nulas (cliente, lead, proveedor).
    """
    from src.integrations.vtiger import VTigerClient, VTigerError

    # Verificar configuración VTiger
    from src.config import get_settings
    settings = get_settings()
    if not settings.vtiger_url or not settings.vtiger_token:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="VTiger no configurado. Establece VTIGER_URL y VTIGER_TOKEN en .env",
        )

    # Login en VTiger
    client = VTigerClient()
    try:
        await client.login()
    except VTigerError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"No se pudo conectar con VTiger: {e}",
        )

    # Obtener contactos locales (excluir nulos/pendientes)
    result = await db.execute(
        select(Contact)
        .where(Contact.category.notin_(["nulo", "pendiente"]))
        .order_by(Contact.name)
    )
    contacts = result.scalars().all()

    results: list[SyncResult] = []
    created = updated = skipped = errors = 0

    for contact in contacts:
        try:
            vtiger_data = {
                "lastname": contact.name.rsplit(" ", 1)[-1] if " " in contact.name else contact.name,
                "firstname": contact.name.rsplit(" ", 1)[0] if " " in contact.name else "",
                "email": contact.email,
                "phone": contact.phone or "",
            }
            if contact.company:
                vtiger_data["account_id"] = contact.company
            if contact.category:
                vtiger_data["cf_categoria"] = contact.category

            if contact.crm_id:
                # Actualizar existente
                await client.update_contact(contact.crm_id, vtiger_data)
                results.append(SyncResult(
                    email=contact.email,
                    name=contact.name,
                    crm_id=contact.crm_id,
                    action="updated",
                ))
                updated += 1
            else:
                # Crear nuevo
                vtiger_id = await client.create_contact(vtiger_data)
                contact.crm_id = vtiger_id
                results.append(SyncResult(
                    email=contact.email,
                    name=contact.name,
                    crm_id=vtiger_id,
                    action="created",
                ))
                created += 1

        except VTigerError as e:
            results.append(SyncResult(
                email=contact.email,
                name=contact.name,
                crm_id=contact.crm_id,
                action="error",
                detail=str(e),
            ))
            errors += 1
        except Exception as e:
            logger.error("Error sync contacto %s: %s", contact.email, e)
            results.append(SyncResult(
                email=contact.email,
                name=contact.name,
                crm_id=contact.crm_id,
                action="error",
                detail=str(e),
            ))
            errors += 1

    # Guardar crm_ids actualizados
    await db.commit()
    await client.close()

    logger.info(
        "CRM sync: %d total, %d creados, %d actualizados, %d errores",
        len(contacts), created, updated, errors,
    )

    return SyncResponse(
        total=len(contacts),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        results=results,
        connected=True,
    )
