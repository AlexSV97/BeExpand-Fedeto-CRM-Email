"""SlaAlertService — SLA-05.

Alertas tempranas de SLA: detecta tickets en riesgo (watch/high/critical) antes
del vencimiento, genera alertas idempotentes (sin duplicar por scans repetidos),
las persiste como ``OperationalRecord`` (``record_kind="sla_alert"``) y notifica
best-effort a analista/coordinación. Se apoya en ``TicketLifecycleService``
(SLA-01..04).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import OperationalRecord
from src.domain.ticketing import Ticket
from src.services.ticket_lifecycle import TicketLifecycleService

logger = logging.getLogger(__name__)

SLA_ALERT_RECORD_KIND = "sla_alert"

_RISK_RANK = {"low": 0, "watch": 1, "high": 2, "critical": 3}
_SEVERITY = {"watch": "warning", "high": "high", "critical": "critical"}
_ALERTING_RISKS = ("watch", "high", "critical")
_NOTIFY_RISKS = ("high", "critical")
# Mapeo de riesgo SLA → urgencia que entiende el notificador de correo.
_RISK_URGENCY = {"watch": "media", "high": "alta", "critical": "alta"}


class SlaAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ticket_id: str
    sla_name: str | None = None
    risk_level: str
    severity: str
    remaining_minutes: float | None = None
    message: str
    acknowledged: bool = False
    created_at: str


class SlaAlertScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned: int
    generated: int
    alerts: list[SlaAlert]


class SlaAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    alerts: list[SlaAlert]


class SlaAlertService:
    def __init__(
        self,
        db: AsyncSession,
        lifecycle: TicketLifecycleService | None = None,
        notifier=None,
    ) -> None:
        self.db = db
        self._lifecycle = lifecycle or TicketLifecycleService()
        self._notifier = notifier

    async def scan(self, tickets: list[Ticket]) -> list[SlaAlert]:
        """Evalúa los tickets y genera alertas tempranas (idempotente)."""
        generated: list[SlaAlert] = []
        for ticket in tickets:
            if ticket.sla is None:
                continue
            assessment = self._lifecycle.assess(ticket)
            risk = assessment.risk_level.value
            if risk not in _ALERTING_RISKS:
                continue
            if await self._is_deduped(ticket.id, risk):
                continue

            alert = await self._persist(ticket, assessment)
            generated.append(alert)
            if risk in _NOTIFY_RISKS:
                await self._notify(ticket, assessment)
        return generated

    async def _is_deduped(self, ticket_id: str, risk: str) -> bool:
        """True si ya hay una alerta sin reconocer de riesgo igual o superior."""
        latest = await self._latest(ticket_id)
        if latest is None:
            return False
        payload = latest.payload or {}
        if payload.get("acknowledged"):
            return False
        prev_risk = payload.get("risk_level", "low")
        return _RISK_RANK.get(prev_risk, 0) >= _RISK_RANK.get(risk, 0)

    async def _persist(self, ticket: Ticket, assessment) -> SlaAlert:
        risk = assessment.risk_level.value
        severity = _SEVERITY.get(risk, "warning")
        remaining = assessment.remaining_minutes
        sla_name = ticket.sla.name if ticket.sla else None
        message = (
            f"SLA {risk} en {ticket.id}"
            + (f" ({sla_name})" if sla_name else "")
            + (f": quedan {remaining:.0f} min" if remaining is not None else "")
        )
        record = OperationalRecord(
            record_kind=SLA_ALERT_RECORD_KIND,
            resource_id=ticket.id,
            actor_kind="system",
            actor_name="sla-monitor",
            status=severity,
            title=message,
            payload={
                "risk_level": risk,
                "severity": severity,
                "remaining_minutes": remaining,
                "sla_name": sla_name,
                "message": message,
                "acknowledged": False,
            },
            created_at=datetime.now(timezone.utc),  # orden determinista (microseg)
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return self._to_alert(record)

    async def _notify(self, ticket: Ticket, assessment) -> None:
        if self._notifier is None or not getattr(self._notifier, "enabled", False):
            return
        try:
            await self._notifier.send_alert(
                subject=f"[SLA {assessment.risk_level.value}] {ticket.subject}",
                sender_name="SLA Monitor",
                sender_email="sla-monitor@beconnect",
                urgency=_RISK_URGENCY.get(assessment.risk_level.value, "alta"),
                category="sla",
                summary=assessment.recommendation,
                action_required=f"Revisar ticket {ticket.id} antes del vencimiento",
            )
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning("SLA notify falló para %s: %s", ticket.id, exc)

    # ── Lectura / ack ────────────────────────────────────────────────────
    async def list_active(self, limit: int = 100) -> list[SlaAlert]:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(OperationalRecord.record_kind == SLA_ALERT_RECORD_KIND)
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(limit)
        )
        alerts = [self._to_alert(r) for r in result.scalars().all()]
        return [a for a in alerts if not a.acknowledged]

    async def acknowledge(self, alert_id: str, actor: str) -> bool:
        record = await self.db.get(OperationalRecord, alert_id)
        if record is None or record.record_kind != SLA_ALERT_RECORD_KIND:
            return False
        payload = dict(record.payload or {})
        payload["acknowledged"] = True
        payload["acknowledged_by"] = actor
        record.payload = payload
        record.status = "acknowledged"
        await self.db.commit()
        return True

    async def _latest(self, ticket_id: str) -> OperationalRecord | None:
        result = await self.db.execute(
            select(OperationalRecord)
            .where(
                OperationalRecord.record_kind == SLA_ALERT_RECORD_KIND,
                OperationalRecord.resource_id == ticket_id,
            )
            .order_by(OperationalRecord.created_at.desc(), OperationalRecord.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_alert(record: OperationalRecord) -> SlaAlert:
        payload = record.payload or {}
        return SlaAlert(
            id=record.id,
            ticket_id=record.resource_id or "",
            sla_name=payload.get("sla_name"),
            risk_level=payload.get("risk_level", ""),
            severity=payload.get("severity", record.status or "warning"),
            remaining_minutes=payload.get("remaining_minutes"),
            message=payload.get("message") or record.title or "",
            acknowledged=bool(payload.get("acknowledged", False)),
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
