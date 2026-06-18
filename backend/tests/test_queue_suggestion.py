"""Tests for CE-02 — AI queue suggestion (QueueSuggestionService + endpoint)."""

import json

import pytest

from src.services.queue_strategy import QueueStrategyService
from src.services.queue_suggestion import (
    QueueSuggestionRequest,
    QueueSuggestionService,
    _clamp_confidence,
    _extract_json,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLLM:
    def __init__(self, response: str, model: str = "fake-model"):
        self._response = response
        self.model = model

    async def generate(self, prompt: str, **kwargs) -> str:
        return self._response


class RaisingLLM:
    model = "fake-model"

    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("LLM backend down")


def _strategy() -> QueueStrategyService:
    return QueueStrategyService()  # hardcoded topology (has known slugs)


def _request(**overrides) -> QueueSuggestionRequest:
    base = dict(
        subject="There is an error and a timeout in production",
        body_text="The service is failing with a timeout, incident in prod",
    )
    base.update(overrides)
    return QueueSuggestionRequest(**base)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_clamp_confidence_bounds(self):
        assert _clamp_confidence(1.7) == 1.0
        assert _clamp_confidence(-0.5) == 0.0
        assert _clamp_confidence(0.42) == 0.42
        assert _clamp_confidence("nope", default=0.3) == 0.3

    def test_extract_json_plain(self):
        assert _extract_json('{"slug": "n2-resolucion"}') == {"slug": "n2-resolucion"}

    def test_extract_json_with_fences(self):
        raw = '```json\n{"slug": "n1-triage", "confidence": 0.8}\n```'
        assert _extract_json(raw)["slug"] == "n1-triage"

    def test_extract_json_prose_returns_none(self):
        assert _extract_json("no json here") is None


# ---------------------------------------------------------------------------
# AI path (Scenario 1, 6)
# ---------------------------------------------------------------------------


class TestSuggestAi:
    async def test_ai_suggests_valid_queue(self):
        llm = FakeLLM(json.dumps({"slug": "n2-resolucion", "confidence": 0.9, "reason": "incident"}))
        svc = QueueSuggestionService(_strategy(), llm_client=llm)

        result = await svc.suggest(_request())

        assert result.source == "ai"
        assert result.recommended.queue.slug == "n2-resolucion"
        assert result.recommended.confidence == 0.9
        assert result.model == "fake-model"

    async def test_ai_confidence_is_clamped(self):
        llm = FakeLLM(json.dumps({"slug": "n1-triage", "confidence": 1.7, "reason": "x"}))
        svc = QueueSuggestionService(_strategy(), llm_client=llm)

        result = await svc.suggest(_request())

        assert result.source == "ai"
        assert result.recommended.confidence == 1.0

    async def test_ai_parses_valid_alternatives_only(self):
        llm = FakeLLM(
            json.dumps(
                {
                    "slug": "n2-resolucion",
                    "confidence": 0.8,
                    "reason": "x",
                    "alternatives": ["n3-ingenieria", "does-not-exist", "n2-resolucion"],
                }
            )
        )
        svc = QueueSuggestionService(_strategy(), llm_client=llm)

        result = await svc.suggest(_request())

        alt_slugs = [a.queue.slug for a in result.alternatives]
        assert alt_slugs == ["n3-ingenieria"]  # unknown + self filtered out


# ---------------------------------------------------------------------------
# Fallback paths (Scenario 2, 3, 4)
# ---------------------------------------------------------------------------


class TestFallback:
    async def test_falls_back_when_llm_raises(self):
        svc = QueueSuggestionService(_strategy(), llm_client=RaisingLLM())
        result = await svc.suggest(_request())
        assert result.source == "rules"
        assert result.model is None

    async def test_falls_back_on_unknown_slug(self):
        llm = FakeLLM(json.dumps({"slug": "does-not-exist", "confidence": 0.9, "reason": "x"}))
        svc = QueueSuggestionService(_strategy(), llm_client=llm)
        result = await svc.suggest(_request())
        assert result.source == "rules"

    async def test_falls_back_on_malformed_json(self):
        llm = FakeLLM("the best queue is probably N2 because it's an incident")
        svc = QueueSuggestionService(_strategy(), llm_client=llm)
        result = await svc.suggest(_request())
        assert result.source == "rules"

    async def test_rules_fallback_routes_incident_to_n2(self):
        svc = QueueSuggestionService(_strategy(), llm_client=RaisingLLM())
        result = await svc.suggest(_request())
        assert result.recommended.queue.slug == "n2-resolucion"


# ---------------------------------------------------------------------------
# Endpoint (Scenario 5) — LLM unreachable in tests → rules fallback
# ---------------------------------------------------------------------------


class TestSuggestionEndpoint:
    async def test_endpoint_returns_suggestion(self, client, auth_headers):
        response = await client.post(
            "/api/v1/queues/suggestion",
            headers=auth_headers,
            json={
                "subject": "Critical incident: error and timeout",
                "body_text": "Production is down with a timeout error",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] in ("ai", "rules")
        assert "recommended" in data
        assert data["recommended"]["queue"]["slug"]

    async def test_endpoint_requires_auth(self, client):
        response = await client.post(
            "/api/v1/queues/suggestion",
            json={"subject": "x", "body_text": "y"},
        )
        assert response.status_code in (401, 403)
