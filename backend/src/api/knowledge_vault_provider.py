"""Single shared Knowledge Vault provider.

Previously the SOC router and the knowledge router each built their own vault
under different ``app.state`` keys (``knowledge_vault_service`` vs
``knowledge_vault``), so they could diverge. This module is the single source of
truth: one canonical ``app.state.knowledge_vault`` instance (seed docs + LLM +
best-effort snapshot persistence) shared by both routers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from src.db.session import async_session_factory
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService
from src.services.knowledge_vault_store import (
    load_knowledge_vault_snapshot,
    save_knowledge_vault_snapshot,
)

logger = logging.getLogger(__name__)

# Canonical app.state key shared by all routers.
_STATE_KEY = "knowledge_vault"


def _seed_knowledge_documents() -> list[KnowledgeDocument]:
    """Return seed documents for the knowledge vault."""
    return [
        KnowledgeDocument(
            id="KB-001",
            title="Password Reset Procedure",
            body=(
                "Step-by-step guide for resetting user passwords in the OTRS portal. "
                "1. Verify user identity via security questions. "
                "2. Generate temporary password. "
                "3. Force password change on next login."
            ),
            document_type="case",
            tags=["password", "security", "authentication"],
        ),
        KnowledgeDocument(
            id="KB-002",
            title="SLA Breach Response Runbook",
            body=(
                "Standard operating procedure for SLA breach notifications. "
                "When SLA exceeds 90% of threshold, notify team lead. "
                "At 100%, escalate to N2 immediately."
            ),
            document_type="runbook",
            tags=["sla", "breach", "escalation", "urgent"],
        ),
        KnowledgeDocument(
            id="KB-003",
            title="VPN Access Troubleshooting",
            body=(
                "Common VPN connection issues and solutions. "
                "Check client version, verify credentials, test network connectivity, "
                "check firewall rules."
            ),
            document_type="faq",
            tags=["vpn", "network", "connectivity"],
        ),
        KnowledgeDocument(
            id="KB-004",
            title="Email Classification Guidelines",
            body=(
                "Rules for classifying incoming emails: "
                "SPAM (unsolicited bulk), PHISHING (suspicious links), "
                "SUPPORT (service requests), BILLING (invoice queries)."
            ),
            document_type="case",
            tags=["email", "classification", "security"],
        ),
        KnowledgeDocument(
            id="KB-005",
            title="Incident Response Plan",
            body=(
                "Tier 1: Acknowledge and categorize. "
                "Tier 2: Investigate and contain. "
                "Tier 3: Eradicate and recover. "
                "Post-incident: Document lessons learned."
            ),
            document_type="runbook",
            tags=["incident", "security", "response"],
        ),
        KnowledgeDocument(
            id="KB-006",
            title="New User Onboarding Checklist",
            body=(
                "Create account, assign mailbox, configure OTRS profile, "
                "set up VPN access, schedule security training, "
                "grant initial permissions."
            ),
            document_type="faq",
            tags=["onboarding", "user", "setup"],
        ),
    ]


async def get_knowledge_vault(request: Request) -> KnowledgeVaultService:
    """Return the single shared knowledge vault (cached on ``app.state``)."""
    svc = getattr(request.app.state, _STATE_KEY, None)
    if isinstance(svc, KnowledgeVaultService):
        return svc

    from src.llm_client import LLMClient
    from src.services.vector_store import VectorStore

    llm_client = LLMClient(use_chat_model=True)

    async def _snapshot_writer(snapshot: dict[str, Any]) -> None:
        # Best-effort: snapshot persistence must never break a request.
        try:
            async with async_session_factory() as writer_session:
                await save_knowledge_vault_snapshot(
                    writer_session,
                    KnowledgeVaultService.from_snapshot(snapshot, llm_client=llm_client),
                )
        except Exception:  # noqa: BLE001 — persistence is an optimization
            logger.warning("knowledge vault snapshot write failed (best-effort)", exc_info=True)

    svc = KnowledgeVaultService(
        documents=_seed_knowledge_documents(),
        vector_store=VectorStore(),
        llm_client=llm_client,
        snapshot_writer=_snapshot_writer,
    )

    # Load/persist snapshot best-effort: the vault must work from seed even if the
    # snapshot store (settings table) is unavailable — resilient in prod, hermetic
    # in tests.
    try:
        async with async_session_factory() as session:
            snapshot = await load_knowledge_vault_snapshot(session)
            if snapshot:
                svc = KnowledgeVaultService.from_snapshot(
                    snapshot, llm_client=llm_client, snapshot_writer=_snapshot_writer
                )
            else:
                await svc.embed_all_documents()
                await save_knowledge_vault_snapshot(session, svc)
    except Exception:  # noqa: BLE001 — fall back to in-memory seed vault
        logger.warning("knowledge vault snapshot load failed; using seed (best-effort)", exc_info=True)
        try:
            await svc.embed_all_documents()
        except Exception:  # noqa: BLE001 — embeddings also best-effort
            pass

    setattr(request.app.state, _STATE_KEY, svc)
    return svc
