"""
Attachment Storage — guarda y recupera adjuntos de emails en el sistema de archivos.

Organización:
  storage/attachments/{email_id}/{filename}

Cada adjunto se almacena en una carpeta por email_id,
lo que facilita la limpieza y la navegación.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Ruta base de almacenamiento ──

def get_storage_base() -> Path:
    """Devuelve la ruta base para almacenamiento de adjuntos.
    
    Usa la variable de entorno STORAGE_PATH si está definida,
    sino usa 'storage/' en la raíz del backend.
    """
    env_path = os.environ.get("BECONNECT_STORAGE_PATH")
    if env_path:
        return Path(env_path)
    # Por defecto: backend/storage/
    return Path(__file__).resolve().parent.parent.parent / "storage"


ATTACHMENTS_DIR = get_storage_base() / "attachments"


# ── Modelo de datos ──

@dataclass
class StoredAttachment:
    """Referencia a un adjunto almacenado en disco."""
    filename: str
    content_type: str
    file_path: str  # Ruta absoluta al archivo
    size: int       # Tamaño en bytes
    stored_at: str  # ISO timestamp


# ── Operaciones ──

def ensure_dirs():
    """Crea los directorios de almacenamiento si no existen."""
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug("Directorios de almacenamiento preparados: %s", ATTACHMENTS_DIR)


def save_attachment(
    email_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> StoredAttachment:
    """Guarda un adjunto en disco y devuelve su referencia.
    
    Args:
        email_id: ID del email al que pertenece el adjunto.
        filename: Nombre original del archivo.
        content_type: Tipo MIME del archivo.
        data: Contenido binario del adjunto.

    Returns:
        StoredAttachment con la información del archivo guardado.
    """
    ensure_dirs()

    # Crear carpeta por email_id
    email_dir = ATTACHMENTS_DIR / email_id
    email_dir.mkdir(parents=True, exist_ok=True)

    # Si ya existe un archivo con el mismo nombre, añadir timestamp
    file_path = email_dir / filename
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = email_dir / f"{stem}_{timestamp}{suffix}"

    # Escribir archivo
    file_path.write_bytes(data)
    file_size = len(data)

    logger.info(
        "Adjunto guardado: %s (%d bytes) → %s",
        filename, file_size, file_path,
    )

    return StoredAttachment(
        filename=filename,
        content_type=content_type,
        file_path=str(file_path.resolve()),
        size=file_size,
        stored_at=datetime.now().isoformat(),
    )


def get_attachments_for_email(email_id: str) -> list[StoredAttachment]:
    """Recupera todos los adjuntos almacenados para un email."""
    email_dir = ATTACHMENTS_DIR / email_id
    if not email_dir.exists():
        return []

    attachments = []
    for f in sorted(email_dir.iterdir()):
        if f.is_file():
            attachments.append(StoredAttachment(
                filename=f.name,
                content_type=_guess_content_type(f.name),
                file_path=str(f.resolve()),
                size=f.stat().st_size,
                stored_at=datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            ))
    return attachments


def delete_attachments_for_email(email_id: str) -> bool:
    """Elimina todos los adjuntos de un email (para limpieza)."""
    email_dir = ATTACHMENTS_DIR / email_id
    if email_dir.exists():
        shutil.rmtree(email_dir)
        logger.info("Adjuntos eliminados para email: %s", email_id)
        return True
    return False


def read_attachment_bytes(file_path: str) -> bytes | None:
    """Lee el contenido binario de un adjunto almacenado."""
    try:
        return Path(file_path).read_bytes()
    except Exception as e:
        logger.error("Error leyendo adjunto %s: %s", file_path, e)
        return None


def _guess_content_type(filename: str) -> str:
    """Adivina el tipo MIME por extensión."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".xml": "application/xml",
        ".zip": "application/zip",
    }
    return mime_map.get(ext, "application/octet-stream")
