from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_current_user
from src.db.models import User
from src.db.session import async_session_factory
from src.services.knowledge_answer import (
    KnowledgeAnswer,
    KnowledgeAnswerRequest,
    KnowledgeAnswerService,
)
from src.services.knowledge_vault import (
    KnowledgeSearchRequest,
    KnowledgeVaultService,
    SimilarCaseRequest,
)
from src.services.knowledge_vault_store import load_knowledge_vault_snapshot, save_knowledge_vault_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])


async def get_knowledge_vault(request: Request) -> KnowledgeVaultService:
    vault = getattr(request.app.state, "knowledge_vault", None)
    if isinstance(vault, KnowledgeVaultService):
        return vault

    async def _snapshot_writer(snapshot: dict[str, object]) -> None:
        try:
            async with async_session_factory() as writer_session:
                await save_knowledge_vault_snapshot(
                    writer_session,
                    KnowledgeVaultService.from_snapshot(snapshot),
                )
        except Exception:  # noqa: BLE001 — persistencia best-effort
            logger.warning("knowledge vault snapshot write failed (best-effort)", exc_info=True)

    # Carga best-effort: el vault debe funcionar aunque el store no esté disponible.
    try:
        async with async_session_factory() as session:
            snapshot = await load_knowledge_vault_snapshot(session)
            if snapshot:
                vault = KnowledgeVaultService.from_snapshot(snapshot, snapshot_writer=_snapshot_writer)
            else:
                vault = KnowledgeVaultService(snapshot_writer=_snapshot_writer)
                await save_knowledge_vault_snapshot(session, vault)
    except Exception:  # noqa: BLE001 — vault en memoria como fallback
        logger.warning("knowledge vault snapshot load failed; using in-memory (best-effort)", exc_info=True)
        vault = KnowledgeVaultService(snapshot_writer=_snapshot_writer)

    request.app.state.knowledge_vault = vault
    return vault


@router.get("/search/knowledge")
async def search_knowledge(
    query: str,
    limit: int = 5,
    customer: str | None = None,
    document_type: str | None = None,
    source_type: str | None = None,
    tags: list[str] | None = None,
    current_user: User = Depends(get_current_user),
    vault: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    request = KnowledgeSearchRequest(
        query=query,
        limit=limit,
        customer=customer,
        document_type=document_type,
        source_type=source_type,
        tags=tags or [],
    )
    return vault.search(request)


@router.post("/search/similar-cases")
async def search_similar_cases(
    request: SimilarCaseRequest,
    current_user: User = Depends(get_current_user),
    vault: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    return vault.similar_cases(request)


@router.post("/search/knowledge/answer", response_model=KnowledgeAnswer)
async def answer_from_knowledge(
    body: KnowledgeAnswerRequest,
    current_user: User = Depends(get_current_user),
    vault: KnowledgeVaultService = Depends(get_knowledge_vault),
):
    """Grounded RAG answer that cites its sources (KV-06)."""
    return await KnowledgeAnswerService(vault).answer(body.query, limit=body.limit)
