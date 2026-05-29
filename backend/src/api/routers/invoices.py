"""
Router de facturas extraídas de adjuntos de email.

GET /api/v1/invoices — lista de facturas con filtros
GET /api/v1/invoices/{id} — detalle de una factura
GET /api/v1/invoices/{id}/download — descargar el PDF original
GET /api/v1/emails/{email_id}/invoices — facturas de un email específico
"""

import logging
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Email, Invoice
from src.db.session import get_db
from src.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invoices"])


@router.get("/invoices")
async def list_invoices(
    proveedor: str | None = Query(None, description="Filtrar por proveedor"),
    fecha_from: date | None = Query(None, description="Fecha factura desde (YYYY-MM-DD)"),
    fecha_to: date | None = Query(None, description="Fecha factura hasta (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lista todas las facturas extraídas."""
    query = select(Invoice).order_by(Invoice.created_at.desc())

    if proveedor:
        query = query.where(Invoice.proveedor.ilike(f"%{proveedor}%"))
    if fecha_from:
        query = query.where(Invoice.fecha >= fecha_from)
    if fecha_to:
        query = query.where(Invoice.fecha <= fecha_to)

    # Total de resultados (sin paginación)
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Paginación
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return {
        "total": total or 0,
        "skip": skip,
        "limit": limit,
        "invoices": [
            {
                "id": inv.id,
                "email_id": inv.email_id,
                "filename": inv.filename,
                "file_size": inv.file_size,
                "numero": inv.numero,
                "proveedor": inv.proveedor,
                "importe": inv.importe,
                "fecha": inv.fecha.isoformat() if inv.fecha else None,
                "vencimiento": inv.vencimiento.isoformat() if inv.vencimiento else None,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }
            for inv in invoices
        ],
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Detalle de una factura con toda la información extraída."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    return {
        "id": inv.id,
        "email_id": inv.email_id,
        "filename": inv.filename,
        "file_path": inv.file_path,
        "file_size": inv.file_size,
        "numero": inv.numero,
        "proveedor": inv.proveedor,
        "importe": inv.importe,
        "fecha": inv.fecha.isoformat() if inv.fecha else None,
        "vencimiento": inv.vencimiento.isoformat() if inv.vencimiento else None,
        "extracted_data": inv.extracted_data or {},
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }


@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Descarga el archivo PDF original de la factura."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    file_path = Path(inv.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(
        path=str(file_path),
        filename=inv.filename,
        media_type="application/pdf",
    )


@router.get("/emails/{email_id}/invoices")
async def get_email_invoices(
    email_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Obtiene las facturas asociadas a un email específico."""
    result = await db.execute(
        select(Invoice).where(Invoice.email_id == email_id)
        .order_by(Invoice.created_at.desc())
    )
    invoices = result.scalars().all()

    return {
        "email_id": email_id,
        "total": len(invoices),
        "invoices": [
            {
                "id": inv.id,
                "filename": inv.filename,
                "file_size": inv.file_size,
                "numero": inv.numero,
                "proveedor": inv.proveedor,
                "importe": inv.importe,
                "fecha": inv.fecha.isoformat() if inv.fecha else None,
                "vencimiento": inv.vencimiento.isoformat() if inv.vencimiento else None,
            }
            for inv in invoices
        ],
    }
