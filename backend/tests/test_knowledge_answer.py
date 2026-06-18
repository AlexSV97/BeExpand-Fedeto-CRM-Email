"""Tests for KV-06 — Knowledge cited answers (KnowledgeAnswerService + endpoint)."""

import pytest

from src.services.knowledge_answer import KnowledgeAnswerService
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.model = "fake-model"

    async def generate(self, prompt: str, **kwargs) -> str:
        return self._response


class RaisingLLM:
    model = "fake-model"

    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("LLM down")


def _vault_with_docs() -> KnowledgeVaultService:
    docs = [
        KnowledgeDocument(
            id="KB-001",
            title="Password reset runbook",
            body="To reset a password, open the admin portal and use the reset flow.",
            document_type="runbook",
            tags=["password", "reset"],
        ),
        KnowledgeDocument(
            id="KB-002",
            title="Portal access issues",
            body="Portal access problems are often resolved by clearing the session.",
            document_type="faq",
            tags=["portal", "access"],
        ),
    ]
    # No llm_client → search_rag falls back to keyword search (no embeddings needed).
    return KnowledgeVaultService(documents=docs)


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestAnswer:
    async def test_ai_answer_cites_sources(self):
        svc = KnowledgeAnswerService(_vault_with_docs(), llm_client=FakeLLM("Usa el flujo de reseteo [1]."))
        res = await svc.answer("password reset")
        assert res.source == "ai"
        assert res.grounded is True
        assert res.answer == "Usa el flujo de reseteo [1]."
        assert len(res.sources) >= 1

    async def test_extractive_fallback_when_llm_fails(self):
        svc = KnowledgeAnswerService(_vault_with_docs(), llm_client=RaisingLLM())
        res = await svc.answer("password reset")
        assert res.source == "extractive"
        assert res.grounded is True
        assert "[1]" in res.answer
        assert len(res.sources) >= 1

    async def test_no_documents_not_grounded(self):
        svc = KnowledgeAnswerService(KnowledgeVaultService(documents=[]), llm_client=FakeLLM("x"))
        res = await svc.answer("nonexistent topic zzz")
        assert res.grounded is False
        assert res.sources == []
        assert res.source == "none"

    async def test_sources_carry_metadata(self):
        svc = KnowledgeAnswerService(_vault_with_docs(), llm_client=RaisingLLM())
        res = await svc.answer("password reset")
        s = res.sources[0]
        assert s.ref == 1
        assert s.id.startswith("KB-")
        assert s.title
        assert s.excerpt


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestAnswerEndpoint:
    async def test_endpoint_returns_answer(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/search/knowledge/answer",
            headers=auth_headers,
            json={"query": "password reset", "limit": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data and "sources" in data
        assert data["source"] in ("ai", "extractive", "none")

    async def test_endpoint_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/search/knowledge/answer",
            json={"query": "password reset"},
        )
        assert resp.status_code == 401
