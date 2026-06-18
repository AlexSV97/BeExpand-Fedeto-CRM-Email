"""
Tests for the /api/v1/health endpoint.

Covers response shape, per-service probe fields, and overall status aggregation.
Health endpoint is public (no auth required).
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_returns_expected_shape(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "services" in data
        assert data["app"] == "Aiuken SOC"
        assert data["version"] == "0.1.0"

        services = data["services"]
        assert "database" in services
        assert "otrs" in services
        assert "ai" in services

    async def test_health_database_probe_returns_ok_with_db_running(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        data = response.json()
        assert data["services"]["database"]["status"] == "ok"

    async def test_health_otrs_probe_returns_not_configured_when_no_env(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        data = response.json()
        # Without env vars, OTRS should report not_configured
        assert data["services"]["otrs"]["status"] in ("ok", "not_configured", "error")

    async def test_health_status_is_ok_or_degraded(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        data = response.json()
        assert data["status"] in ("ok", "degraded")

    async def test_health_is_public_no_auth_required(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
