"""Ticket ingestion router for Aiuken SOC over OTRS/Znuny."""

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.db.models import User
from src.domain.ticketing import Ticket, TicketIngestionInput
from src.services.ticket_ingestion import (
    TicketIngestionService,
    get_ticket_ingestion_service,
)

router = APIRouter(tags=["tickets"])


@router.post("/tickets/ingest", response_model=Ticket)
async def ingest_ticket_from_email(
    body: TicketIngestionInput,
    current_user: User = Depends(get_current_user),
    service: TicketIngestionService = Depends(get_ticket_ingestion_service),
):
    """Convierte un email interno en ticket canónico y crea el ticket en OTRS/Znuny."""
    return await service.ingest_email(body)
