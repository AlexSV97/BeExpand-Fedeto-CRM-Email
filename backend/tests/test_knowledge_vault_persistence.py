from __future__ import annotations

import pytest

from src.domain.ticketing import Article, ActorKind, Queue, Ticket, TicketState
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService
from src.services.knowledge_vault_store import load_knowledge_vault_snapshot, save_knowledge_vault_snapshot
from src.services.vector_store import VectorStore
from tests.conftest import TestSession


class FakeEmbeddingLLM:
    async def generate_embedding(self, text: str):
        return [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_knowledge_vault_snapshot_roundtrip():
    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-1",
                title="WAF rule tuning",
                body="Update the WAF rule after a false positive.",
                customer="Aiuken",
                tags=["waf"],
            )
        ],
        vector_store=VectorStore(),
    )
    vault._vector_store.add("doc-1", [0.1, 0.2, 0.3])
    vault._embeddings_done = True

    snapshot = vault.to_snapshot()
    restored = KnowledgeVaultService.from_snapshot(snapshot)

    assert restored.documents[0].id == "doc-1"
    assert restored._vector_store.search([0.1, 0.2, 0.3], limit=1)[0][0] == "doc-1"


@pytest.mark.asyncio
async def test_knowledge_vault_snapshot_persists_to_settings_table():
    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-2",
                title="VPN onboarding",
                body="Provide VPN profile and MFA setup.",
                customer="Aiuken",
                tags=["vpn"],
            )
        ]
    )

    async with TestSession() as session:
        await save_knowledge_vault_snapshot(session, vault)
        snapshot = await load_knowledge_vault_snapshot(session)

    assert snapshot is not None
    assert snapshot["documents"][0]["id"] == "doc-2"


@pytest.mark.asyncio
async def test_embed_all_documents_triggers_snapshot_writer():
    calls: list[dict] = []

    async def writer(snapshot: dict):
        calls.append(snapshot)

    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-3",
                title="VPN onboarding",
                body="Provide VPN profile and MFA setup.",
                customer="Aiuken",
                tags=["vpn"],
            )
        ],
        vector_store=VectorStore(),
        llm_client=FakeEmbeddingLLM(),
        snapshot_writer=writer,
    )

    count = await vault.embed_all_documents()

    assert count == 1
    assert calls
    assert calls[0]["documents"][0]["id"] == "doc-3"


@pytest.mark.asyncio
async def test_ingest_closed_tickets_only_indexes_closed_items():
    vault = KnowledgeVaultService(llm_client=FakeEmbeddingLLM())
    tickets = [
        Ticket(
            id="T-1",
            subject="Open issue",
            queue=Queue(name="Support", slug="support"),
            state=TicketState.OPEN,
            articles=[Article(id="A-1", ticket_id="T-1", author_kind=ActorKind.HUMAN, author_name="User", body_text="open")],
        ),
        Ticket(
            id="T-2",
            subject="Resolved issue",
            queue=Queue(name="Support", slug="support"),
            state=TicketState.RESOLVED,
            articles=[Article(id="A-2", ticket_id="T-2", author_kind=ActorKind.HUMAN, author_name="User", body_text="resolved")],
        ),
    ]

    count = await vault.ingest_closed_tickets(tickets, embed=False)

    assert count == 1
    assert [doc.source_id for doc in vault.documents] == ["T-2"]
