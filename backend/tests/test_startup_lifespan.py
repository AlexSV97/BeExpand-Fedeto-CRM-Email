from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.api import main
from src.api.routers import knowledge as knowledge_router
from src.domain.ticketing import ActorKind, Article, Queue, Ticket, TicketPriority, TicketState
from tests.conftest import TestSession


class _DummySessionFactory:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeVault:
    def __init__(self, documents=None, llm_client=None, snapshot_writer=None):
        self.documents = list(documents or [])
        self.snapshot_writer = snapshot_writer
        self.ingested_ticket_ids: list[str] = []

    @classmethod
    def from_snapshot(cls, snapshot, *, llm_client=None, snapshot_writer=None):
        documents = [doc if hasattr(doc, "id") else SimpleNamespace(**doc) for doc in snapshot.get("documents", [])]
        return cls(documents=documents, llm_client=llm_client, snapshot_writer=snapshot_writer)

    def add_document_with_embedding(self, document):
        self.documents.append(document)

    async def ingest_closed_tickets(self, tickets, *, embed=True):
        ingested = 0
        for ticket in tickets:
            if ticket.state in {TicketState.RESOLVED, TicketState.CLOSED, TicketState.MERGED}:
                self.ingested_ticket_ids.append(ticket.id)
                self.documents.append(SimpleNamespace(id=f"ticket-{ticket.id}", source_id=ticket.id))
                ingested += 1
        return ingested

    def to_snapshot(self):
        def _dump(doc):
            if hasattr(doc, "model_dump"):
                return doc.model_dump(mode="json")
            if hasattr(doc, "__dict__"):
                return dict(doc.__dict__)
            return doc

        return {"documents": [_dump(doc) for doc in self.documents]}


@pytest.mark.asyncio
async def test_lifespan_seeds_knowledge_vault_during_startup(monkeypatch):
    calls: list[str] = []

    async def fake_init_db():
        calls.append("init_db")

    async def fake_recover_orphan_tasks():
        calls.append("recover_orphan_tasks")

    async def fake_seed_admin():
        calls.append("seed_admin")

    async def fake_seed_queues():
        calls.append("seed_queues")

    async def fake_seed_knowledge_vault():
        calls.append("seed_knowledge_vault")

    async def fake_check_production_settings():
        calls.append("check_production_settings")

    async def fake_auto_sync_loop():
        calls.append("auto_sync_loop_started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("auto_sync_loop_cancelled")
            raise

    async def fake_sla_alert_loop():
        calls.append("sla_alert_loop_started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("sla_alert_loop_cancelled")
            raise

    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main, "_recover_orphan_tasks", fake_recover_orphan_tasks)
    monkeypatch.setattr(main, "seed_admin", fake_seed_admin)
    monkeypatch.setattr(main, "seed_queues", fake_seed_queues)
    monkeypatch.setattr(main, "seed_knowledge_vault", fake_seed_knowledge_vault)
    monkeypatch.setattr(main, "_check_production_settings", fake_check_production_settings)
    monkeypatch.setattr(main, "_auto_sync_loop", fake_auto_sync_loop)
    monkeypatch.setattr(main, "_sla_alert_loop", fake_sla_alert_loop)

    async with main.lifespan(object()):
        await asyncio.sleep(0)

    assert calls[:6] == [
        "init_db",
        "recover_orphan_tasks",
        "seed_admin",
        "seed_queues",
        "seed_knowledge_vault",
        "check_production_settings",
    ]
    assert "auto_sync_loop_started" in calls
    assert "sla_alert_loop_started" in calls
    assert "auto_sync_loop_cancelled" in calls
    assert "sla_alert_loop_cancelled" in calls


@pytest.mark.asyncio
async def test_seed_knowledge_vault_merges_snapshot_and_demo_tickets(monkeypatch):
    saved_snapshots: list[dict] = []

    async def fake_load_snapshot(session):
        return {
            "documents": [
                {
                    "id": "KB-001",
                    "title": "Existing password reset",
                    "body": "Existing snapshot entry",
                    "source_type": "ticket",
                    "document_type": "case",
                    "source_id": "LEGACY-1",
                }
            ]
        }

    async def fake_save_snapshot(session, vault):
        saved_snapshots.append(vault.to_snapshot())

    async def fake_resolve_tickets_with_mode(otrs, count):
        return [
            Ticket(
                id="T-OPEN",
                subject="Open issue",
                queue=Queue(name="Support", slug="support"),
                state=TicketState.OPEN,
                priority=TicketPriority.MEDIUM,
                articles=[Article(id="A-1", ticket_id="T-OPEN", author_kind=ActorKind.HUMAN, author_name="User", body_text="open")],
            ),
            Ticket(
                id="T-CLOSED",
                subject="Closed issue",
                queue=Queue(name="Support", slug="support"),
                state=TicketState.RESOLVED,
                priority=TicketPriority.HIGH,
                articles=[Article(id="A-2", ticket_id="T-CLOSED", author_kind=ActorKind.HUMAN, author_name="User", body_text="closed")],
            ),
        ], "demo"

    class _FakeSettings:
        is_configured = False

    class _FakeLLMClient:
        def __init__(self, use_chat_model=True):
            self.use_chat_model = use_chat_model

    monkeypatch.setattr(main, "async_session_factory", lambda: _DummySessionFactory())
    monkeypatch.setattr("src.api.routers.soc._resolve_tickets_with_mode", fake_resolve_tickets_with_mode)
    monkeypatch.setattr("src.services.knowledge_vault_store.load_knowledge_vault_snapshot", fake_load_snapshot)
    monkeypatch.setattr("src.services.knowledge_vault_store.save_knowledge_vault_snapshot", fake_save_snapshot)
    monkeypatch.setattr("src.services.knowledge_vault.KnowledgeVaultService", _FakeVault)
    monkeypatch.setattr("src.integrations.otrs_znuny.settings.OtrsZnunySettings", lambda: _FakeSettings())
    monkeypatch.setattr("src.llm_client.LLMClient", _FakeLLMClient)

    await main.seed_knowledge_vault()

    assert len(saved_snapshots) == 1
    document_ids = [doc["id"] for doc in saved_snapshots[0]["documents"]]
    assert "KB-001" in document_ids
    assert any(doc_id.startswith("ticket-T-CLOSED") for doc_id in document_ids)
    assert all(doc_id != "ticket-T-OPEN" for doc_id in document_ids)


@pytest.mark.asyncio
async def test_startup_seed_is_visible_through_knowledge_search(client, auth_headers, monkeypatch):
    async def noop(*args, **kwargs):
        return None

    class _FakeSettings:
        is_configured = False

    class _FakeLLMClient:
        def __init__(self, use_chat_model=True):
            self.use_chat_model = use_chat_model

        async def generate_embedding(self, text: str):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(main, "init_db", noop)
    monkeypatch.setattr(main, "_recover_orphan_tasks", noop)
    monkeypatch.setattr(main, "seed_admin", noop)
    monkeypatch.setattr(main, "seed_queues", noop)
    monkeypatch.setattr(main, "_check_production_settings", noop)
    monkeypatch.setattr(main, "_auto_sync_loop", lambda: asyncio.sleep(3600))
    monkeypatch.setattr(main, "_sla_alert_loop", lambda: asyncio.sleep(3600))
    monkeypatch.setattr(main, "async_session_factory", TestSession)
    monkeypatch.setattr("src.integrations.otrs_znuny.settings.OtrsZnunySettings", lambda: _FakeSettings())
    monkeypatch.setattr("src.llm_client.LLMClient", _FakeLLMClient)
    monkeypatch.setattr(knowledge_router, "async_session_factory", TestSession)
    monkeypatch.setattr(main.app.state, "knowledge_vault", None, raising=False)

    async with main.lifespan(main.app):
        await asyncio.sleep(0)

    response = await client.get(
        "/api/v1/search/knowledge",
        params={"query": "password reset", "limit": 5},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["items"][0]["document"]["id"] == "KB-001"
