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
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) > 0

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
