from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import SLA, Ticket, TicketState


class TicketLifecycleStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class SlaRiskLevel(str, Enum):
    LOW = "low"
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class TicketLifecycleProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: TicketState
    lifecycle_state: TicketLifecycleStatus
    stop_sla: bool
    reason: str


class SlaAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    state: TicketState
    lifecycle_state: TicketLifecycleStatus
    stop_sla: bool
    solution_time_minutes: int | None = None
    elapsed_minutes: float | None = None
    remaining_minutes: float | None = None
    risk_level: SlaRiskLevel = SlaRiskLevel.LOW
    recommendation: str
    reason: str
    as_of: datetime


class TicketLifecycleService:
    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def state_profile(self, state: TicketState) -> TicketLifecycleProfile:
        if state in {TicketState.NEW, TicketState.OPEN}:
            return TicketLifecycleProfile(
                state=state,
                lifecycle_state=TicketLifecycleStatus.RUNNING,
                stop_sla=False,
                reason="State keeps the SLA clock running.",
            )

        if state is TicketState.PENDING:
            return TicketLifecycleProfile(
                state=state,
                lifecycle_state=TicketLifecycleStatus.PAUSED,
                stop_sla=True,
                reason="Pending pauses the SLA clock until the ticket is reopened.",
            )

        return TicketLifecycleProfile(
            state=state,
            lifecycle_state=TicketLifecycleStatus.STOPPED,
            stop_sla=True,
            reason="Closed or merged tickets stop the SLA clock permanently.",
        )

    def assess(self, ticket: Ticket, as_of: datetime | None = None) -> SlaAssessment:
        as_of = as_of or self._now_provider()
        profile = self.state_profile(ticket.state)
        solution_time_minutes = self._solution_time_minutes(ticket.sla)

        if solution_time_minutes is None:
            return SlaAssessment(
                ticket_id=ticket.id,
                state=ticket.state,
                lifecycle_state=profile.lifecycle_state,
                stop_sla=profile.stop_sla,
                recommendation="No SLA configured for this ticket.",
                reason=profile.reason,
                as_of=as_of,
            )

        elapsed_minutes = self._elapsed_minutes(ticket, profile, as_of)
        remaining_minutes = max(solution_time_minutes - elapsed_minutes, 0.0)
        risk_level = self._risk_level(solution_time_minutes, remaining_minutes)

        return SlaAssessment(
            ticket_id=ticket.id,
            state=ticket.state,
            lifecycle_state=profile.lifecycle_state,
            stop_sla=profile.stop_sla,
            solution_time_minutes=solution_time_minutes,
            elapsed_minutes=elapsed_minutes,
            remaining_minutes=remaining_minutes,
            risk_level=risk_level,
            recommendation=self._recommendation(profile, remaining_minutes, solution_time_minutes, risk_level),
            reason=profile.reason,
            as_of=as_of,
        )

    @staticmethod
    def _solution_time_minutes(sla: SLA | None) -> int | None:
        if sla is None:
            return None
        return sla.solution_time_minutes

    def _elapsed_minutes(self, ticket: Ticket, profile: TicketLifecycleProfile, as_of: datetime) -> float:
        end_time = as_of
        if profile.stop_sla:
            end_time = min(ticket.updated_at, as_of)
        elapsed = (end_time - ticket.created_at).total_seconds() / 60.0
        return max(round(elapsed, 2), 0.0)

    @staticmethod
    def _risk_level(solution_time_minutes: int, remaining_minutes: float) -> SlaRiskLevel:
        if remaining_minutes <= 0:
            return SlaRiskLevel.CRITICAL

        remaining_ratio = remaining_minutes / float(solution_time_minutes)
        if remaining_ratio <= 0.25:
            return SlaRiskLevel.HIGH
        if remaining_ratio < 0.75:
            return SlaRiskLevel.WATCH
        return SlaRiskLevel.LOW

    @staticmethod
    def _recommendation(
        profile: TicketLifecycleProfile,
        remaining_minutes: float,
        solution_time_minutes: int,
        risk_level: SlaRiskLevel,
    ) -> str:
        base = {
            SlaRiskLevel.LOW: "SLA is healthy",
            SlaRiskLevel.WATCH: "SLA needs attention soon",
            SlaRiskLevel.HIGH: "SLA is at risk",
            SlaRiskLevel.CRITICAL: "SLA is exhausted",
        }[risk_level]
        if profile.stop_sla:
            return f"{base}; the SLA is currently paused or stopped. Remaining budget: {remaining_minutes:.0f} minutes out of {solution_time_minutes}."
        return f"{base}. Remaining budget: {remaining_minutes:.0f} minutes out of {solution_time_minutes}."


async def get_ticket_lifecycle_service() -> TicketLifecycleService:
    yield TicketLifecycleService()
