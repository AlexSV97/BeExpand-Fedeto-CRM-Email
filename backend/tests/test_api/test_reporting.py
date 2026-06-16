from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api.main import app
from src.services.reporting import FeedbackLoopService, ReportingService


@pytest.mark.asyncio
async def test_reporting_endpoints_return_daily_and_weekly_reports(client, auth_headers):
    as_of = datetime(2026, 6, 16, 11, 0, tzinfo=timezone.utc)
    app.state.reporting_service = ReportingService(now_provider=lambda: as_of)

    try:
        daily_response = await client.post(
            "/api/v1/reporting/daily",
            headers=auth_headers,
            json={
                "as_of": "2026-06-16T11:00:00Z",
                "tickets": [
                    {
                        "id": "daily-open",
                        "subject": "Daily open ticket",
                        "queue": {"name": "Support"},
                        "state": "open",
                        "priority": "normal",
                        "sla": {"name": "Standard", "solution_time_minutes": 120},
                        "created_at": "2026-06-16T10:00:00Z",
                        "updated_at": "2026-06-16T10:00:00Z",
                    }
                ],
                "knowledge_documents": [],
            },
        )

        weekly_response = await client.post(
            "/api/v1/reporting/weekly",
            headers=auth_headers,
            json={
                "as_of": "2026-06-16T11:00:00Z",
                "tickets": [
                    {
                        "id": "weekly-closed",
                        "subject": "Weekly closed ticket",
                        "queue": {"name": "Support"},
                        "state": "closed",
                        "priority": "normal",
                        "sla": {"name": "Standard", "solution_time_minutes": 60},
                        "created_at": "2026-06-15T09:00:00Z",
                        "updated_at": "2026-06-15T10:00:00Z",
                    }
                ],
                "knowledge_documents": [
                    {
                        "id": "kb-1",
                        "title": "SLA breach runbook",
                        "body": "Use this article when a ticket breaches SLA.",
                    }
                ],
            },
        )
    finally:
        app.state.reporting_service = None

    assert daily_response.status_code == 200
    daily_payload = daily_response.json()
    assert daily_payload["window"] == "daily"
    assert daily_payload["metrics"]["total_tickets"] == 1
    assert daily_payload["metrics"]["backlog_tickets"] == 1

    assert weekly_response.status_code == 200
    weekly_payload = weekly_response.json()
    assert weekly_payload["window"] == "weekly"
    assert weekly_payload["metrics"]["total_tickets"] == 1
    assert weekly_payload["metrics"]["knowledge_documents"] == 1


@pytest.mark.asyncio
async def test_feedback_endpoint_returns_deterministic_suggestions(client, auth_headers):
    app.state.feedback_loop_service = FeedbackLoopService()

    try:
        first_response = await client.post(
            "/api/v1/reporting/feedback",
            headers=auth_headers,
            json={
                "analyst_name": "Analyst One",
                "target": "copilot-response",
                "verdict": "revise",
                "comment": "The response was too verbose and the wrong queue was suggested.",
                "tags": ["copilot", "routing"],
            },
        )

        second_response = await client.post(
            "/api/v1/reporting/feedback",
            headers=auth_headers,
            json={
                "analyst_name": "Analyst Two",
                "target": "weekly-report",
                "verdict": "accept",
                "comment": "The knowledge article for SLA breach handling is missing.",
                "tags": ["knowledge", "sla"],
            },
        )
    finally:
        app.state.feedback_loop_service = None

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["total_feedback"] == 1
    assert {item["kind"] for item in first_payload["suggestions"]} == {"rule", "prompt_placeholder"}

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["total_feedback"] == 2
    assert {item["kind"] for item in second_payload["suggestions"]} == {"runbook"}
