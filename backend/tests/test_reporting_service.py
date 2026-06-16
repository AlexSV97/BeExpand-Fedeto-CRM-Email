from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.ticketing import Queue, SLA, Ticket, TicketPriority, TicketState


def _ticket(*, ticket_id: str, state: TicketState, created_at: datetime, updated_at: datetime, solution_time_minutes: int) -> Ticket:
    return Ticket(
        id=ticket_id,
        subject=f"Ticket {ticket_id}",
        queue=Queue(name="Support"),
        state=state,
        priority=TicketPriority.NORMAL,
        sla=SLA(
            id=f"SLA-{ticket_id}",
            name="Standard",
            solution_time_minutes=solution_time_minutes,
        ),
        created_at=created_at,
        updated_at=updated_at,
    )


def test_daily_report_calculates_metrics_and_recommendations():
    from src.services.reporting import OperationalReportRequest, ReportWindow, ReportingService

    as_of = datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc)
    service = ReportingService(now_provider=lambda: as_of)

    report = service.generate_report(
        OperationalReportRequest(
            window=ReportWindow.DAILY,
            as_of=as_of,
            tickets=[
                _ticket(
                    ticket_id="open-1",
                    state=TicketState.OPEN,
                    created_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
                    solution_time_minutes=120,
                ),
                _ticket(
                    ticket_id="pending-1",
                    state=TicketState.PENDING,
                    created_at=datetime(2026, 6, 16, 10, 15, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 6, 16, 10, 30, tzinfo=timezone.utc),
                    solution_time_minutes=30,
                ),
                _ticket(
                    ticket_id="closed-1",
                    state=TicketState.CLOSED,
                    created_at=datetime(2026, 6, 16, 9, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 6, 16, 10, 50, tzinfo=timezone.utc),
                    solution_time_minutes=45,
                ),
            ],
        )
    )

    assert report.window == ReportWindow.DAILY
    assert report.metrics.total_tickets == 3
    assert report.metrics.open_tickets == 1
    assert report.metrics.pending_tickets == 1
    assert report.metrics.closed_tickets == 1
    assert report.metrics.backlog_tickets == 2
    assert report.metrics.sla_breaches == 1
    assert report.metrics.sla_compliance_rate == pytest.approx(2 / 3, rel=1e-3)
    assert {item.kind for item in report.recommendations} == {"rule", "runbook", "prompt_placeholder"}


def test_weekly_report_with_empty_snapshot_keeps_metrics_zero():
    from src.services.reporting import OperationalReportRequest, ReportWindow, ReportingService

    as_of = datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc)
    service = ReportingService(now_provider=lambda: as_of)

    report = service.generate_report(
        OperationalReportRequest(
            window=ReportWindow.WEEKLY,
            as_of=as_of,
            tickets=[],
            knowledge_documents=[],
        )
    )

    assert report.window == ReportWindow.WEEKLY
    assert report.metrics.total_tickets == 0
    assert report.metrics.backlog_tickets == 0
    assert report.metrics.sla_compliance_rate == 0.0
    assert report.recommendations == []


def test_feedback_loop_turns_analyst_comments_into_deterministic_suggestions():
    from src.services.reporting import AnalystFeedbackRequest, FeedbackLoopService

    service = FeedbackLoopService()

    response = service.record_feedback(
        AnalystFeedbackRequest(
            analyst_name="Analyst One",
            target="copilot-response",
            verdict="revise",
            comment="The response was too verbose, the wrong queue was suggested, and we need a runbook for this case.",
            tags=["copilot", "routing"],
        )
    )

    assert response.total_feedback == 1
    assert {item.kind for item in response.suggestions} == {"rule", "runbook", "prompt_placeholder"}
    assert any("queue" in item.title.lower() for item in response.suggestions)
    assert any("runbook" in item.title.lower() for item in response.suggestions)


def test_feedback_loop_handles_missing_knowledge_as_runbook_work():
    from src.services.reporting import AnalystFeedbackRequest, FeedbackLoopService

    service = FeedbackLoopService()

    response = service.record_feedback(
        AnalystFeedbackRequest(
            analyst_name="Analyst Two",
            target="weekly-report",
            verdict="accept",
            comment="The knowledge article for SLA breach handling is missing.",
            tags=["knowledge", "sla"],
        )
    )

    assert response.total_feedback == 1
    assert {item.kind for item in response.suggestions} == {"runbook"}
    assert response.suggestions[0].source == "feedback"
