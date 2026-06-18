"""EscalationRecordService — CE-04.

Persistencia y consulta del historial de escalados. Cada escalado se guarda como
un ``OperationalRecord`` con ``record_kind="escalation"`` (sin tabla nueva,
igual que agent_recommendation/agent_approval/audit_event), almacenando el
``EscalationPlan`` completo (CE-03) en el payload.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import OperationalRecord
from src.services.escalation import EscalationPlan

ESCALATION_RECORD_KIND = "escalation"


class EscalationHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str
    actor_name: str | None = None
    from_tier: str | None = None
    to_tier: str | None = None
    to_queue: str | None = None
    level: int | None = None
    should_escalate: bool = False
    reason: str | None = None
    created_at: str


class EscalationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    total: int
    items: list[EscalationHistoryItem]


class EscalationRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        *,
        ticket_id: str,
        actor_name: str,
        plan: EscalationPlan,
        reason: str | None = None,
    ) -> OperationalRecord:
        """Persiste un escalado como OperationalRecord (REQ-1, REQ-2)."""
        record = OperationalRecord(
            record_kind=ESCALATION_RECORD_KIND,
            resource_id=ticket_id,
            actor_kind="human",
            actor_name=actor_name,
            status="escalated" if plan.should_escalate else "noop",
            title=f"Escalado {plan.from_tier.value} → {plan.to_tier.value}",
            payload={
                "plan": plan.model_dump(mode="json"),
                "reason": reason if reason is not None else plan.reason,
            },
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def list_for_ticket(self, ticket_id: str, limit: int = 50) -> list[OperationalRecord]:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(
                OperationalRecord.record_kind == ESCALATION_RECORD_KIND,
                OperationalRecord.resource_id == ticket_id,
            )
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_all(self, limit: int = 50) -> list[OperationalRecord]:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(OperationalRecord.record_kind == ESCALATION_RECORD_KIND)
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def to_item(record: OperationalRecord) -> EscalationHistoryItem:
        payload = record.payload or {}
        plan = payload.get("plan") or {}
        to_queue = plan.get("to_queue") or {}
        return EscalationHistoryItem(
            id=record.id,
            ticket_id=record.resource_id or "",
            actor_name=record.actor_name,
            from_tier=plan.get("from_tier"),
            to_tier=plan.get("to_tier"),
            to_queue=to_queue.get("slug") if isinstance(to_queue, dict) else None,
            level=plan.get("level"),
            should_escalate=bool(plan.get("should_escalate", record.status == "escalated")),
            reason=payload.get("reason") or plan.get("reason"),
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
