"""SLA lifecycle router for BeConnect AI over OTRS/Znuny."""

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.db.models import User
from src.domain.ticketing import Ticket
from src.services.ticket_lifecycle import (
    SlaAssessment,
    TicketLifecycleService,
    get_ticket_lifecycle_service,
)

router = APIRouter(tags=["sla"])


@router.post("/tickets/sla/status", response_model=SlaAssessment)
async def assess_ticket_sla(
    body: Ticket,
    current_user: User = Depends(get_current_user),
    service: TicketLifecycleService = Depends(get_ticket_lifecycle_service),
):
    return service.assess(body)
