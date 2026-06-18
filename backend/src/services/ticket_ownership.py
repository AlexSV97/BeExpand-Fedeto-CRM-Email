"""TicketOwnershipService — CE-05.

Gestión rastreable de propietario (owner) y bloqueo (lock) por ticket. Cada
cambio se persiste como ``OperationalRecord`` con ``record_kind="ownership"``
(sin tabla nueva, patrón de CE-04), guardando un snapshot completo del estado
resultante. El estado actual es el snapshot del registro más reciente.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import OperationalRecord

OWNERSHIP_RECORD_KIND = "ownership"


class OwnershipState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str | None = None
    locked: bool = False
    locked_by: str | None = None


class OwnershipHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str
    action: str
    actor: str | None = None
    owner: str | None = None
    locked: bool = False
    locked_by: str | None = None
    reason: str | None = None
    created_at: str


class OwnershipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    state: OwnershipState
    history: list[OwnershipHistoryItem]


class TicketOwnershipService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Acciones ─────────────────────────────────────────────────────────
    async def assign(self, ticket_id: str, owner: str, actor_name: str, reason: str | None = None) -> OperationalRecord:
        prev = await self.current_state(ticket_id)
        new = OwnershipState(owner=owner, locked=prev.locked, locked_by=prev.locked_by)
        return await self._record(ticket_id, "assign", actor_name, new, reason)

    async def lock(self, ticket_id: str, actor_name: str, reason: str | None = None) -> OperationalRecord:
        prev = await self.current_state(ticket_id)
        new = OwnershipState(owner=prev.owner or actor_name, locked=True, locked_by=actor_name)
        return await self._record(ticket_id, "lock", actor_name, new, reason)

    async def unlock(self, ticket_id: str, actor_name: str, reason: str | None = None) -> OperationalRecord:
        prev = await self.current_state(ticket_id)
        new = OwnershipState(owner=prev.owner, locked=False, locked_by=None)
        return await self._record(ticket_id, "unlock", actor_name, new, reason)

    async def _record(
        self,
        ticket_id: str,
        action: str,
        actor_name: str,
        state: OwnershipState,
        reason: str | None,
    ) -> OperationalRecord:
        record = OperationalRecord(
            record_kind=OWNERSHIP_RECORD_KIND,
            resource_id=ticket_id,
            actor_kind="human",
            actor_name=actor_name,
            status=action,
            title=f"{action} {ticket_id}",
            payload={
                "action": action,
                "actor": actor_name,
                "reason": reason,
                "state": state.model_dump(),
            },
            # Precisión de microsegundo para orden determinista: el
            # server_default de SQLite (CURRENT_TIMESTAMP) es de segundo y
            # empataría varios cambios del mismo flujo (assign→lock→unlock).
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    # ── Lectura ──────────────────────────────────────────────────────────
    async def _latest(self, ticket_id: str) -> OperationalRecord | None:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(
                OperationalRecord.record_kind == OWNERSHIP_RECORD_KIND,
                OperationalRecord.resource_id == ticket_id,
            )
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def current_state(self, ticket_id: str) -> OwnershipState:
        record = await self._latest(ticket_id)
        if record is None:
            return OwnershipState()
        state = (record.payload or {}).get("state") or {}
        return OwnershipState(
            owner=state.get("owner"),
            locked=bool(state.get("locked", False)),
            locked_by=state.get("locked_by"),
        )

    async def list_history(self, ticket_id: str, limit: int = 50) -> list[OperationalRecord]:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(
                OperationalRecord.record_kind == OWNERSHIP_RECORD_KIND,
                OperationalRecord.resource_id == ticket_id,
            )
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def to_item(record: OperationalRecord) -> OwnershipHistoryItem:
        payload = record.payload or {}
        state = payload.get("state") or {}
        return OwnershipHistoryItem(
            id=record.id,
            ticket_id=record.resource_id or "",
            action=payload.get("action") or record.status or "",
            actor=payload.get("actor") or record.actor_name,
            owner=state.get("owner"),
            locked=bool(state.get("locked", False)),
            locked_by=state.get("locked_by"),
            reason=payload.get("reason"),
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
