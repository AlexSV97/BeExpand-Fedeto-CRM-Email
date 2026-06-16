from datetime import datetime, timezone

import pytest

from src.domain.ticketing import Queue, SLA, Ticket, TicketPriority, TicketState
from src.services.ticket_lifecycle import TicketLifecycleService


def _ticket(
    *,
    state: TicketState,
    created_at: datetime,
    updated_at: datetime,
    solution_time_minutes: int,
) -> Ticket:
    return Ticket(
        id="TCK-1",
        subject="Printer is down",
        queue=Queue(name="Support"),
        state=state,
        priority=TicketPriority.NORMAL,
        sla=SLA(
            id="SLA-1",
            name="Standard",
            solution_time_minutes=solution_time_minutes,
        ),
        created_at=created_at,
        updated_at=updated_at,
    )


def test_state_profile_marks_stop_sla_states_and_running_states():
    service = TicketLifecycleService(now_provider=lambda: datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc))

    open_profile = service.state_profile(TicketState.OPEN)
    pending_profile = service.state_profile(TicketState.PENDING)
    closed_profile = service.state_profile(TicketState.CLOSED)
    merged_profile = service.state_profile(TicketState.MERGED)

    assert open_profile.lifecycle_state == "running"
    assert open_profile.stop_sla is False
    assert pending_profile.lifecycle_state == "paused"
    assert pending_profile.stop_sla is True
    assert closed_profile.lifecycle_state == "stopped"
    assert closed_profile.stop_sla is True
    assert merged_profile.lifecycle_state == "stopped"
    assert merged_profile.stop_sla is True


def test_pending_ticket_freezes_elapsed_minutes_at_last_update():
    service = TicketLifecycleService(now_provider=lambda: datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc))
    ticket = _ticket(
        state=TicketState.PENDING,
        created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 16, 10, 20, tzinfo=timezone.utc),
        solution_time_minutes=60,
    )

    assessment = service.assess(ticket)

    assert assessment.lifecycle_state == "paused"
    assert assessment.stop_sla is True
    assert assessment.elapsed_minutes == 20.0
    assert assessment.remaining_minutes == 40.0
    assert assessment.risk_level == "watch"


@pytest.mark.parametrize(
    ("as_of", "solution_time_minutes", "expected_remaining", "expected_risk"),
    [
        (
            datetime(2026, 6, 16, 10, 30, tzinfo=timezone.utc),
            120,
            90.0,
            "low",
        ),
        (
            datetime(2026, 6, 16, 10, 45, tzinfo=timezone.utc),
            60,
            15.0,
            "high",
        ),
        (
            datetime(2026, 6, 16, 11, 10, tzinfo=timezone.utc),
            60,
            0.0,
            "critical",
        ),
    ],
)
def test_risk_recommendation_changes_with_remaining_budget(
    as_of: datetime,
    solution_time_minutes: int,
    expected_remaining: float,
    expected_risk: str,
):
    service = TicketLifecycleService(now_provider=lambda: as_of)
    ticket = _ticket(
        state=TicketState.OPEN,
        created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
        solution_time_minutes=solution_time_minutes,
    )

    assessment = service.assess(ticket)

    assert assessment.remaining_minutes == expected_remaining
    assert assessment.risk_level == expected_risk
    assert assessment.recommendation
