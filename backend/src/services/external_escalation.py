"""ExternalEscalationService — CE-06.

Escalado de un ticket a un destino externo (fabricante / ITSM externo). Enruta a
la cola especial correspondiente (CE-01), genera una referencia de tracking
(`ExternalRef`) y persiste el handoff como ``OperationalRecord`` con
``record_kind="external_escalation"`` (sin tabla nueva, patrón de CE-04/CE-05).

La entrega real a la API del fabricante/ITSM queda fuera de alcance: el artefacto
duradero y consultable es la referencia de tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import OperationalRecord
from src.domain.ticketing import ExternalRef
from src.services.queue_strategy import QueueStrategyService

EXTERNAL_ESCALATION_RECORD_KIND = "external_escalation"

DESTINATION_QUEUE: dict[str, str] = {
    "fabricante": "special-fabricante",
    "external_itsm": "special-external-itsm",
}
DESTINATION_PREFIX: dict[str, str] = {
    "fabricante": "FAB",
    "external_itsm": "ITSM",
}


class ExternalEscalationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    destination: str
    queue_slug: str
    tracking_ref: ExternalRef
    status: str = "sent"
    created_at: str


class ExternalEscalationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    total: int
    items: list[ExternalEscalationResult]


class ExternalEscalationService:
    def __init__(self, db: AsyncSession, strategy: QueueStrategyService) -> None:
        self.db = db
        self._strategy = strategy

    def _resolve_queue_slug(self, destination: str) -> str:
        slug = DESTINATION_QUEUE.get(destination)
        if slug is None:
            raise ValueError(f"Unknown external destination: {destination}")
        specials = {n.queue.slug for n in self._strategy.topology().special_queues}
        if slug not in specials:
            raise ValueError(f"Special queue '{slug}' not found in topology")
        return slug

    def _make_tracking_ref(self, destination: str, external_id: str | None) -> ExternalRef:
        if not external_id:
            prefix = DESTINATION_PREFIX.get(destination, "EXT")
            external_id = f"{prefix}-{uuid4().hex[:8].upper()}"
        return ExternalRef(
            system=destination,
            entity_type="external_case",
            external_id=external_id,
        )

    async def escalate(
        self,
        *,
        ticket_id: str,
        destination: str,
        actor_name: str,
        reason: str | None = None,
        external_id: str | None = None,
    ) -> ExternalEscalationResult:
        """Enruta a destino externo, genera tracking ref y persiste el handoff."""
        queue_slug = self._resolve_queue_slug(destination)  # raises on invalid
        tracking = self._make_tracking_ref(destination, external_id)

        record = OperationalRecord(
            record_kind=EXTERNAL_ESCALATION_RECORD_KIND,
            resource_id=ticket_id,
            actor_kind="human",
            actor_name=actor_name,
            status="sent",
            title=f"External handoff {ticket_id} → {destination}",
            payload={
                "destination": destination,
                "queue_slug": queue_slug,
                "tracking_ref": tracking.model_dump(mode="json"),
                "reason": reason,
                "actor": actor_name,
            },
            created_at=datetime.now(timezone.utc),  # orden determinista (microseg)
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return self.to_item(record)

    async def list_for_ticket(self, ticket_id: str, limit: int = 50) -> list[OperationalRecord]:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(
                OperationalRecord.record_kind == EXTERNAL_ESCALATION_RECORD_KIND,
                OperationalRecord.resource_id == ticket_id,
            )
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def to_item(record: OperationalRecord) -> ExternalEscalationResult:
        payload = record.payload or {}
        ref = payload.get("tracking_ref") or {}
        return ExternalEscalationResult(
            ticket_id=record.resource_id or "",
            destination=payload.get("destination") or "",
            queue_slug=payload.get("queue_slug") or "",
            tracking_ref=ExternalRef.model_validate(ref) if ref else ExternalRef(
                system=payload.get("destination") or "unknown",
                entity_type="external_case",
                external_id="",
            ),
            status=record.status or "sent",
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
