"""
Router de Ajustes del sistema.

Endpoints:
    GET  /settings/imap             -- Configuracion IMAP (password enmascarada)
    PUT  /settings/imap             -- Actualizar configuracion IMAP
    GET  /settings/notifications    -- Configuracion WhatsApp (token enmascarado)
    PUT  /settings/notifications    -- Actualizar configuracion WhatsApp
    PUT  /settings/password         -- Cambiar contrasena del admin
    POST /settings/test-imap        -- Probar conexion IMAP
    POST /settings/test-whatsapp    -- Enviar notificacion de prueba
    GET  /settings/status           -- Health check del sistema

Todas requieren autenticacion (admin).
"""

import logging
import socket
import time
from datetime import datetime, timezone
from typing import Optional

import imaplib
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.config import get_settings
from src.db.models import ClassificationHistory, Setting, User
from src.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def mask_value(value: str, visible: int = 4) -> str:
    """Enmascara un valor sensible, mostrando solo los ultimos N caracteres."""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


# -- IMAP --

class ImapSettings(BaseModel):
    server: str
    port: int
    email: str
    password: str  # Enmascarada en GET, real en PUT
    poll_interval_minutes: int
    folder_map: dict[str, str]


class ImapUpdate(BaseModel):
    server: Optional[str] = None
    port: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None
    poll_interval_minutes: Optional[int] = None
    folder_map: Optional[dict[str, str]] = None


# -- Notificaciones --

class NotificationSettings(BaseModel):
    whatsapp_access_token: str  # Enmascarado en GET
    whatsapp_phone_number_id: str
    whatsapp_to_phone: str
    whatsapp_min_urgency: str


class NotificationUpdate(BaseModel):
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_to_phone: Optional[str] = None
    whatsapp_min_urgency: Optional[str] = None


# -- Password --

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


# -- Test resultados --

class TestImapRequest(BaseModel):
    server: str
    port: int
    email: str
    password: str


class TestImapResponse(BaseModel):
    success: bool
    message: str
    folders: list[str] = []


class TestWhatsAppResponse(BaseModel):
    success: bool
    message: str


# -- Status --

class SystemStatus(BaseModel):
    imap_configured: bool
    whatsapp_configured: bool
    openrouter_configured: bool
    crm_configured: bool
    last_sync_at: Optional[str] = None
    last_retrain_at: Optional[str] = None
    last_retrain_accuracy: Optional[float] = None
    uptime_seconds: Optional[float] = None
    database: str
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Helpers de persistencia
# ---------------------------------------------------------------------------

async def _get_setting(db: AsyncSession, key: str) -> str | None:
    """Lee un setting de la BD, o None si no existe."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def _set_setting(db: AsyncSession, key: str, value: str):
    """Guarda o actualiza un setting en la BD."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    await db.flush()


def _is_masked(value: str) -> bool:
    """Detecta si un valor esta enmascarado (solo asteriscos + quizas 4 chars)."""
    return value.startswith("*") if value else False


# ---------------------------------------------------------------------------
# IMAP Settings
# ---------------------------------------------------------------------------

@router.get("/imap", response_model=ImapSettings)
async def get_imap_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna configuracion IMAP con contrasena enmascarada."""
    settings = get_settings()
    db_password = await _get_setting(db, "imap_password")

    real_password = db_password if db_password is not None else settings.imap_password
    return ImapSettings(
        server=await _get_setting(db, "imap_server") or settings.imap_server,
        port=int(await _get_setting(db, "imap_port") or settings.imap_port),
        email=await _get_setting(db, "imap_email") or settings.imap_email,
        password=mask_value(real_password),
        poll_interval_minutes=int(
            await _get_setting(db, "imap_poll_interval_minutes")
            or settings.imap_poll_interval_minutes
        ),
        folder_map=settings.imap_folder_map,
    )


@router.put("/imap", response_model=ImapSettings)
async def update_imap_settings(
    body: ImapUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza configuracion IMAP."""
    if body.server is not None:
        await _set_setting(db, "imap_server", body.server)
    if body.port is not None:
        await _set_setting(db, "imap_port", str(body.port))
    if body.email is not None:
        await _set_setting(db, "imap_email", str(body.email))
    if body.password is not None and not _is_masked(body.password):
        await _set_setting(db, "imap_password", body.password)
    if body.poll_interval_minutes is not None:
        await _set_setting(db, "imap_poll_interval_minutes", str(body.poll_interval_minutes))

    await db.commit()

    settings = get_settings()
    db_password = await _get_setting(db, "imap_password")
    real_password = db_password if db_password is not None else settings.imap_password

    return ImapSettings(
        server=await _get_setting(db, "imap_server") or settings.imap_server,
        port=int(await _get_setting(db, "imap_port") or settings.imap_port),
        email=await _get_setting(db, "imap_email") or settings.imap_email,
        password=mask_value(real_password),
        poll_interval_minutes=int(
            await _get_setting(db, "imap_poll_interval_minutes")
            or settings.imap_poll_interval_minutes
        ),
        folder_map=settings.imap_folder_map,
    )


@router.post("/test-imap", response_model=TestImapResponse)
async def test_imap_connection(
    body: TestImapRequest,
    current_user: User = Depends(get_current_user),
):
    """Prueba la conexion IMAP con las credenciales proporcionadas."""
    try:
        imap = imaplib.IMAP4_SSL(body.server, body.port, timeout=10)
        imap.login(body.email, body.password)

        # Listar carpetas disponibles
        result, data = imap.list()
        folders: list[str] = []
        if result == "OK":
            for item in data:
                decoded = item.decode("utf-8", errors="replace")
                # Formato tipico: '(\\HasNoChildren) "/" "INBOX"'
                parts = decoded.split('"/"')
                if len(parts) > 1:
                    folder = parts[-1].strip().strip('" ')
                    if folder:
                        folders.append(folder)

        imap.logout()
        return TestImapResponse(
            success=True,
            message=f"Conexion exitosa a {body.server}",
            folders=folders[:20],
        )
    except imaplib.IMAP4.error as e:
        return TestImapResponse(
            success=False,
            message=f"Error IMAP: {e}",
        )
    except socket.timeout:
        return TestImapResponse(
            success=False,
            message=f"Timeout conectando a {body.server}:{body.port}",
        )
    except Exception as e:
        return TestImapResponse(
            success=False,
            message=f"Error de conexion: {e}",
        )


# ---------------------------------------------------------------------------
# Notificaciones (WhatsApp Business)
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna configuracion de notificaciones con token enmascarado."""
    settings = get_settings()
    db_token = await _get_setting(db, "whatsapp_access_token")
    real_token = db_token if db_token is not None else settings.whatsapp_access_token

    return NotificationSettings(
        whatsapp_access_token=mask_value(real_token) if real_token else "",
        whatsapp_phone_number_id=(
            await _get_setting(db, "whatsapp_phone_number_id")
            or settings.whatsapp_phone_number_id
        ),
        whatsapp_to_phone=(
            await _get_setting(db, "whatsapp_to_phone")
            or settings.whatsapp_to_phone
        ),
        whatsapp_min_urgency=(
            await _get_setting(db, "whatsapp_min_urgency")
            or settings.whatsapp_min_urgency
        ),
    )


@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    body: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza configuracion de notificaciones WhatsApp."""
    if body.whatsapp_access_token is not None and not _is_masked(body.whatsapp_access_token):
        await _set_setting(db, "whatsapp_access_token", body.whatsapp_access_token)
    if body.whatsapp_phone_number_id is not None:
        await _set_setting(db, "whatsapp_phone_number_id", body.whatsapp_phone_number_id)
    if body.whatsapp_to_phone is not None:
        await _set_setting(db, "whatsapp_to_phone", body.whatsapp_to_phone)
    if body.whatsapp_min_urgency is not None:
        await _set_setting(db, "whatsapp_min_urgency", body.whatsapp_min_urgency)

    await db.commit()

    settings = get_settings()
    db_token = await _get_setting(db, "whatsapp_access_token")
    real_token = db_token if db_token is not None else settings.whatsapp_access_token

    return NotificationSettings(
        whatsapp_access_token=mask_value(real_token) if real_token else "",
        whatsapp_phone_number_id=(
            await _get_setting(db, "whatsapp_phone_number_id")
            or settings.whatsapp_phone_number_id
        ),
        whatsapp_to_phone=(
            await _get_setting(db, "whatsapp_to_phone")
            or settings.whatsapp_to_phone
        ),
        whatsapp_min_urgency=(
            await _get_setting(db, "whatsapp_min_urgency")
            or settings.whatsapp_min_urgency
        ),
    )


@router.post("/test-whatsapp", response_model=TestWhatsAppResponse)
async def test_whatsapp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Envia un mensaje de prueba a WhatsApp Business."""
    from src.notifiers.whatsapp import WhatsAppNotifier

    settings = get_settings()
    db_token = await _get_setting(db, "whatsapp_access_token")
    db_phone_number_id = await _get_setting(db, "whatsapp_phone_number_id")
    db_to_phone = await _get_setting(db, "whatsapp_to_phone")

    token = db_token if db_token is not None else settings.whatsapp_access_token
    phone_number_id = db_phone_number_id if db_phone_number_id is not None else settings.whatsapp_phone_number_id
    to_phone = db_to_phone if db_to_phone is not None else settings.whatsapp_to_phone

    if not token:
        return TestWhatsAppResponse(success=False, message="Token de WhatsApp no configurado")
    if not phone_number_id:
        return TestWhatsAppResponse(success=False, message="Phone Number ID no configurado")
    if not to_phone:
        return TestWhatsAppResponse(success=False, message="Teléfono destino no configurado")

    try:
        import httpx

        text = (
            "⚠️ Prueba de Notificación - BeConnect\n\n"
            "Si recibes este mensaje, la integración con WhatsApp Business funciona correctamente.\n\n"
            f"Enviado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to_phone,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            result = response.json()

        if result.get("messages"):
            return TestWhatsAppResponse(success=True, message="Mensaje de prueba enviado correctamente a WhatsApp")
        else:
            error_desc = result.get("error", {}).get("message", "desconocido")
            return TestWhatsAppResponse(
                success=False,
                message=f"Error WhatsApp API: {error_desc}",
            )
    except ImportError:
        return TestWhatsAppResponse(success=False, message="httpx no esta instalado")
    except Exception as e:
        return TestWhatsAppResponse(success=False, message=f"Error de conexion: {e}")


# ---------------------------------------------------------------------------
# Cambio de contrasena
# ---------------------------------------------------------------------------

@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contrasena del usuario autenticado."""
    if not bcrypt.verify(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contrasena actual no es correcta",
        )

    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contrasena debe tener al menos 6 caracteres",
        )

    current_user.hashed_password = bcrypt.hash(body.new_password)
    await db.flush()
    await db.commit()


# ---------------------------------------------------------------------------
# Estado del sistema
# ---------------------------------------------------------------------------

_start_time = time.time()


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Health check detallado del sistema."""
    settings = get_settings()
    db_url = settings.database_url
    db_type = "postgresql" if "postgresql" in db_url else "sqlite"

    # Ultima sincronizacion
    last_sync: str | None = None
    try:
        from src.db.models import Account
        result = await db.execute(
            select(Account).where(Account.email_user == settings.imap_email)
        )
        account = result.scalar_one_or_none()
        if account and account.last_polled_at:
            last_sync = account.last_polled_at.isoformat()
    except Exception:
        pass

    # Ultimo re-entrenamiento
    last_retrain: str | None = None
    last_acc: float | None = None
    try:
        result = await db.execute(
            select(ClassificationHistory)
            .where(ClassificationHistory.method == "ml_classifier_retrain")
            .order_by(ClassificationHistory.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            last_retrain = row.created_at.isoformat() if row.created_at else None
            if row.details and isinstance(row.details, dict):
                last_acc = row.details.get("accuracy")
    except Exception:
        pass

    return SystemStatus(
        imap_configured=bool(
            settings.imap_email
            and settings.imap_password
        ),
        whatsapp_configured=bool(
            settings.whatsapp_access_token
            and settings.whatsapp_phone_number_id
            and settings.whatsapp_to_phone
        ),
        openrouter_configured=bool(settings.openrouter_api_key),
        crm_configured=bool(settings.vtiger_url),
        last_sync_at=last_sync,
        last_retrain_at=last_retrain,
        last_retrain_accuracy=last_acc,
        uptime_seconds=time.time() - _start_time,
        database=db_type,
    )
