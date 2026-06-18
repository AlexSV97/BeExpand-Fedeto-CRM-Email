from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.api.knowledge_vault_provider import get_knowledge_vault
from src.db.models import User
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

router = APIRouter(tags=["knowledge"])


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
