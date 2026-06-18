"""
Tests for the SOC aggregation router endpoints.

Covers all 9 GET endpoints and all 3 POST action endpoints with both
success and failure cases.

Uses the shared `client` and `auth_headers` fixtures from conftest.py,
which provide an SQLite in-memory database, seeded admin user, and a
valid JWT token.
"""

import pytest
from httpx import AsyncClient

from src.api.main import app
from src.api.routers.soc import get_otrs_client
from src.domain.ticketing import Queue, Ticket, TicketPriority, TicketState


def _live_ticket(ticket_id: str = "TICKET-1000") -> Ticket:
    return Ticket(
        id=ticket_id,
        subject="Live OTRS ticket",
        queue=Queue(name="Support", slug="support"),
        state=TicketState.OPEN,
        priority=TicketPriority.HIGH,
        customer_email="live@example.com",
        articles=[],
    )


class _LiveOtrsClient:
    def __init__(self) -> None:
        self.list_tickets_calls = 0
        self.get_ticket_calls: list[str] = []
        self.update_ticket_calls: list[tuple[str, dict]] = []
        self.add_article_calls: list[tuple[str, str]] = []

    async def list_tickets(self, *, limit: int = 50, offset: int = 0, queue: str | None = None):
        self.list_tickets_calls += 1
        return [_live_ticket("TCK-LIVE-1")]

    async def get_ticket(self, ticket_id: str):
        self.get_ticket_calls.append(ticket_id)
        return _live_ticket(ticket_id)

    async def update_ticket(self, ticket_id: str, **kwargs):
        self.update_ticket_calls.append((ticket_id, kwargs))
        return _live_ticket(ticket_id)

    async def add_article(self, ticket_id: str, article):
        self.add_article_calls.append((ticket_id, getattr(article, "body_text", "")))
        from src.domain.ticketing import Article, ActorKind

        return Article(
            id="ART-LIVE-1",
            ticket_id=ticket_id,
            author_kind=ActorKind.HUMAN,
            author_name=getattr(article, "author_name", "admin"),
            body_text=getattr(article, "body_text", ""),
        )


class _BrokenOtrsClient:
    async def list_tickets(self, *, limit: int = 50, offset: int = 0, queue: str | None = None):
        raise RuntimeError("OTRS down")


# ===========================================================================
# GET /soc/command-center
# ===========================================================================

class TestGetCommandCenter:
    async def test_returns_kpi_cards_and_alerts(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/command-center", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "kpiCards" in data
        assert "recentAlerts" in data
        assert "queuePressure" in data
        assert "surfaceStatus" in data
        assert isinstance(data["kpiCards"], list)
        assert len(data["kpiCards"]) > 0
        assert isinstance(data["recentAlerts"], list)
        assert len(data["recentAlerts"]) > 0

    async def test_accepts_period_param(self, client: AsyncClient, auth_headers: dict[str, str]):
        for period in ("24h", "7d", "30d"):
            response = await client.get(
                "/api/v1/soc/command-center",
                params={"period": period},
                headers=auth_headers,
            )
            assert response.status_code == 200

    async def test_rejects_invalid_period(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/command-center",
            params={"period": "invalid"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/command-center")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/tickets
# ===========================================================================

class TestGetTicketQueue:
    async def test_returns_tickets_and_filters(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/tickets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tickets" in data
        assert "total" in data
        assert "page" in data
        assert "filters" in data
        assert "operatingMode" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) > 0

    async def test_returns_operating_mode(self, client: AsyncClient, auth_headers: dict[str, str]):
        """operatingMode should be 'demo' when OTRS is not configured."""
        response = await client.get("/api/v1/soc/tickets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["operatingMode"] == "demo"

    async def test_returns_live_mode_when_otrs_is_configured(self, client: AsyncClient, auth_headers: dict[str, str]):
        app.dependency_overrides[get_otrs_client] = lambda: _LiveOtrsClient()
        try:
            response = await client.get("/api/v1/soc/tickets", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        data = response.json()
        assert data["operatingMode"] == "live"
        assert any(ticket["id"] == "TCK-LIVE-1" for ticket in data["tickets"])

    async def test_returns_degraded_mode_when_otrs_errors(self, client: AsyncClient, auth_headers: dict[str, str]):
        app.dependency_overrides[get_otrs_client] = lambda: _BrokenOtrsClient()
        try:
            response = await client.get("/api/v1/soc/tickets", headers=auth_headers)
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        data = response.json()
        assert data["operatingMode"] == "degraded"

    async def test_supports_pagination(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/tickets",
            params={"page": 1, "limit": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tickets"]) <= 5
        assert data["page"] == 1

    async def test_filters_by_status(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/tickets",
            params={"status": "open"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for ticket in data["tickets"]:
            assert ticket["status"] == "open"

    async def test_filters_by_priority(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/tickets",
            params={"priority": "urgent"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for ticket in data["tickets"]:
            assert ticket["priority"] == "urgent"

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/tickets")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/tickets/{ticket_id}/copilot
# ===========================================================================

class TestGetTicketCopilot:
    async def test_returns_conversation_and_suggestions(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/copilot",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "conversation" in data
        assert "suggestedActions" in data
        assert "ticketContext" in data
        assert isinstance(data["conversation"], list)
        assert len(data["conversation"]) > 0
        assert data["ticketContext"]["ticketId"] == "TICKET-1000"

    async def test_returns_article_count_greater_than_zero(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Synthetic tickets should have 1-3 articles each."""
        response = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/copilot",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ticketContext"]["articleCount"] > 0

    async def test_accepts_message_param(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/tickets/TICKET-1001/copilot",
            params={"message": "What is the status?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # The user message should be in conversation
        messages = [m for m in data["conversation"] if m["role"] == "user"]
        assert len(messages) > 0

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/tickets/TICKET-1000/copilot")
        assert response.status_code == 401

    async def test_uses_otrs_ticket_when_configured(self, client: AsyncClient, auth_headers: dict[str, str]):
        fake_otrs = _LiveOtrsClient()
        app.dependency_overrides[get_otrs_client] = lambda: fake_otrs
        try:
            response = await client.get(
                "/api/v1/soc/tickets/TICKET-LIVE-1/copilot",
                headers=auth_headers,
                params={"message": "Please review"},
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        data = response.json()
        assert data["ticketContext"]["ticketId"] == "TICKET-LIVE-1"
        assert fake_otrs.get_ticket_calls == ["TICKET-LIVE-1"]

    async def test_copilot_reports_live_mode(self, client: AsyncClient, auth_headers: dict[str, str]):
        app.dependency_overrides[get_otrs_client] = lambda: _LiveOtrsClient()
        try:
            response = await client.get(
                "/api/v1/soc/tickets/TICKET-LIVE-1/copilot", headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)
        assert response.status_code == 200
        assert response.json()["operatingMode"] == "live"

    async def test_copilot_reports_demo_mode(self, client: AsyncClient, auth_headers: dict[str, str]):
        # No OTRS configured → demo seed mode.
        response = await client.get(
            "/api/v1/soc/tickets/TICKET-1000/copilot", headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["operatingMode"] == "demo"

    async def test_copilot_reports_degraded_mode(self, client: AsyncClient, auth_headers: dict[str, str]):
        # OTRS configured but failing get_ticket → degraded (synthetic fallback).
        class _BrokenGet:
            async def list_tickets(self, **kwargs):
                return []

            async def get_ticket(self, ticket_id):
                raise RuntimeError("OTRS down")

        app.dependency_overrides[get_otrs_client] = lambda: _BrokenGet()
        try:
            response = await client.get(
                "/api/v1/soc/tickets/TICKET-1000/copilot", headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)
        assert response.status_code == 200
        assert response.json()["operatingMode"] == "degraded"


# ===========================================================================
# GET /soc/sla
# ===========================================================================

class TestGetSlaWarRoom:
    async def test_returns_breach_timers_and_escalations(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/sla", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "breachTimers" in data
        assert "escalations" in data
        assert "activeSLAs" in data
        assert isinstance(data["breachTimers"], list)
        assert len(data["breachTimers"]) > 0

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/sla")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/knowledge
# ===========================================================================

class TestGetKnowledgeVault:
    async def test_returns_articles_and_categories(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/knowledge", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data
        assert "categories" in data
        assert "searchSuggestions" in data
        assert isinstance(data["articles"], list)

    async def test_supports_search(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/knowledge",
            params={"search": "bgp"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_supports_category_filter(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/knowledge",
            params={"category": "runbook"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/knowledge")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/agents
# ===========================================================================

class TestGetAgentGovernance:
    async def test_returns_agents_and_permissions(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/agents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "permissions" in data
        assert "compliance" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) > 0

    async def test_filters_by_status(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/agents",
            params={"status": "active"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for agent in data["agents"]:
            assert agent["status"] == "active"

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/agents")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/reports
# ===========================================================================

class TestGetReports:
    async def test_returns_metrics_and_trends(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/reports", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "trends" in data
        assert "reportTypes" in data
        assert isinstance(data["metrics"], list)
        assert len(data["metrics"]) > 0
        assert isinstance(data["trends"], list)
        assert len(data["trends"]) > 0

    async def test_supports_report_type_param(self, client: AsyncClient, auth_headers: dict[str, str]):
        for rtype in ("daily", "weekly", "monthly", "sla", "agent"):
            response = await client.get(
                "/api/v1/soc/reports",
                params={"reportType": rtype},
                headers=auth_headers,
            )
            assert response.status_code == 200

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/reports")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/audit
# ===========================================================================

class TestGetAudit:
    async def test_returns_events_and_actors(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/audit", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "actors" in data
        assert "timeRange" in data
        assert isinstance(data["events"], list)

    async def test_supports_pagination(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get(
            "/api/v1/soc/audit",
            params={"page": 1, "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/audit")
        assert response.status_code == 401


# ===========================================================================
# GET /soc/config
# ===========================================================================

class TestGetConfiguration:
    async def test_returns_settings_and_thresholds(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert "thresholds" in data
        assert "featureFlags" in data
        assert isinstance(data["settings"], list)
        assert len(data["settings"]) > 0
        assert isinstance(data["thresholds"], list)
        assert len(data["thresholds"]) > 0

    async def test_otrs_settings_in_config(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.get("/api/v1/soc/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        settings = {s["key"]: s for s in data["settings"]}

        assert "otrs_configured" in settings
        assert settings["otrs_configured"]["type"] == "boolean"
        # Without env vars, otrs_configured should be false
        assert settings["otrs_configured"]["value"] is False

        assert "otrs_base_url" in settings
        assert settings["otrs_base_url"]["type"] == "string"
        # Without env vars, base_url should be empty
        assert settings["otrs_base_url"]["value"] == ""

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/soc/config")
        assert response.status_code == 401


# ===========================================================================
# POST /soc/tickets/{ticket_id}/reclassify
# ===========================================================================

class TestPostReclassifyTicket:
    async def test_reclassifies_with_valid_priority(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/reclassify",
            headers=auth_headers,
            json={"priority": "urgent", "reason": "Testing reclassification"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reclassified"
        assert data["ticket_id"] == "TICKET-1000"
        assert data["new_priority"] == "urgent"

    async def test_rejects_invalid_priority(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/reclassify",
            headers=auth_headers,
            json={"priority": "invalid", "reason": "Test"},
        )
        assert response.status_code == 422

    async def test_rejects_empty_reason_too_long(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/reclassify",
            headers=auth_headers,
            json={"priority": "high", "reason": "x" * 501},
        )
        assert response.status_code == 422

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/reclassify",
            json={"priority": "high", "reason": "Test"},
        )
        assert response.status_code == 401

    async def test_updates_otrs_when_configured(self, client: AsyncClient, auth_headers: dict[str, str]):
        fake_otrs = _LiveOtrsClient()
        app.dependency_overrides[get_otrs_client] = lambda: fake_otrs
        try:
            response = await client.post(
                "/api/v1/soc/tickets/TICKET-LIVE-1/reclassify",
                headers=auth_headers,
                json={"priority": "urgent", "reason": "Needs higher priority"},
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        assert fake_otrs.update_ticket_calls
        ticket_id, kwargs = fake_otrs.update_ticket_calls[0]
        assert ticket_id == "TICKET-LIVE-1"
        assert "priority" in kwargs


# ===========================================================================
# POST /soc/tickets/{ticket_id}/escalate
# ===========================================================================

class TestPostEscalateTicket:
    async def test_escalates_with_valid_reason(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "Testing escalation", "target_tier": "n2"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "escalated"
        assert data["ticket_id"] == "TICKET-1000"
        assert "escalation_level" in data
        assert "target_queue" in data

    async def test_escalates_without_target_tier(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1001/escalate",
            headers=auth_headers,
            json={"reason": "Default escalation"},
        )
        assert response.status_code == 200

    async def test_rejects_empty_reason(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "   ", "target_tier": "n2"},
        )
        assert response.status_code == 422

    async def test_rejects_missing_reason(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"target_tier": "n2"},
        )
        assert response.status_code == 422

    async def test_rejects_invalid_target_tier(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "Testing", "target_tier": "invalid"},
        )
        assert response.status_code == 422

    async def test_rejects_reason_too_long(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            headers=auth_headers,
            json={"reason": "x" * 501, "target_tier": "n2"},
        )
        assert response.status_code == 422

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/escalate",
            json={"reason": "Testing", "target_tier": "n2"},
        )
        assert response.status_code == 401

    async def test_updates_otrs_when_configured(self, client: AsyncClient, auth_headers: dict[str, str]):
        fake_otrs = _LiveOtrsClient()
        app.dependency_overrides[get_otrs_client] = lambda: fake_otrs
        try:
            response = await client.post(
                "/api/v1/soc/tickets/TICKET-LIVE-1/escalate",
                headers=auth_headers,
                json={"reason": "Escalate to N2", "target_tier": "n2"},
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        assert fake_otrs.update_ticket_calls


# ===========================================================================
# POST /soc/tickets/{ticket_id}/notes
# ===========================================================================

class TestPostAddNote:
    async def test_adds_note_with_valid_content(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "Test internal note", "visibility": "internal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["ticket_id"] == "TICKET-1000"
        assert "note_id" in data

    async def test_adds_note_with_customer_visibility(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "Customer-facing note", "visibility": "customer"},
        )
        assert response.status_code == 200

    async def test_rejects_empty_content(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "", "visibility": "internal"},
        )
        assert response.status_code == 422

    async def test_rejects_whitespace_only_content(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "   ", "visibility": "internal"},
        )
        assert response.status_code == 422

    async def test_rejects_invalid_visibility(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "Test", "visibility": "public"},
        )
        assert response.status_code == 422

    async def test_rejects_content_too_long(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            headers=auth_headers,
            json={"content": "x" * 5001, "visibility": "internal"},
        )
        assert response.status_code == 422

    async def test_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/soc/tickets/TICKET-1000/notes",
            json={"content": "Test", "visibility": "internal"},
        )
        assert response.status_code == 401

    async def test_adds_otrs_article_when_configured(self, client: AsyncClient, auth_headers: dict[str, str]):
        fake_otrs = _LiveOtrsClient()
        app.dependency_overrides[get_otrs_client] = lambda: fake_otrs
        try:
            response = await client.post(
                "/api/v1/soc/tickets/TICKET-LIVE-1/notes",
                headers=auth_headers,
                json={"content": "This is an internal note", "visibility": "internal"},
            )
        finally:
            app.dependency_overrides.pop(get_otrs_client, None)

        assert response.status_code == 200
        assert fake_otrs.add_article_calls
