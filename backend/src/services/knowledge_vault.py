from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import Ticket, TicketState
from src.llm_client import LLMClient
from src.services.vector_store import VectorStore


# KV-01: estados que marcan un ticket como "cerrado" e ingerible al vault.
_CLOSED_STATES = {TicketState.RESOLVED, TicketState.CLOSED, TicketState.MERGED}


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "of", "on", "or", "please",
    "show", "the", "to", "we", "what", "when", "with", "you",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9áéíóúñü]+", text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def _safe_join(parts: list[str]) -> str:
    return " ".join(part for part in parts if part).strip()


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    body: str
    source_type: str = "ticket"
    document_type: str = "case"
    source_id: str | None = None
    customer: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    limit: int = 5
    customer: str | None = None
    document_type: str | None = None
    source_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class SimilarCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body_text: str = ""
    customer: str | None = None
    tags: list[str] = Field(default_factory=list)
    limit: int = 5


class KnowledgeSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: KnowledgeDocument
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    explanation: str


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    total: int
    items: list[KnowledgeSearchResult]


class SimilarCasesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    total: int
    items: list[KnowledgeSearchResult]


@dataclass(slots=True)
class _DocumentScore:
    document: KnowledgeDocument
    score: float
    matched_terms: list[str]
    explanation: str


class KnowledgeVaultService:
    def __init__(
        self,
        documents: list[KnowledgeDocument] | None = None,
        vector_store: VectorStore | None = None,
        llm_client: LLMClient | None = None,
    ):
        self._documents = documents or []
        self._vector_store = vector_store or VectorStore()
        self._llm_client = llm_client
        self._embeddings_done = False

    @property
    def documents(self) -> list[KnowledgeDocument]:
        return list(self._documents)

    def add_document(self, document: KnowledgeDocument) -> None:
        self._documents.append(document)

    def add_document_with_embedding(self, document: KnowledgeDocument) -> None:
        """Add a document and schedule embedding generation."""
        self._documents.append(document)
        # Embedding will be generated on next embed_all_documents() call
        self._embeddings_done = False

    # ── KV-01: ingesta de tickets cerrados ───────────────────────────────
    def has_document(self, source_id: str, source_type: str = "ticket") -> bool:
        return any(
            d.source_id == source_id and d.source_type == source_type
            for d in self._documents
        )

    def ingest_ticket(self, ticket: Ticket) -> KnowledgeDocument | None:
        """Indexa un ticket como documento de conocimiento (case). Dedup por id.

        Devuelve el documento creado, o None si ya estaba ingerido.
        """
        if self.has_document(ticket.id, "ticket"):
            return None

        body_parts: list[str] = []
        for article in ticket.articles:
            text = (article.body_text or article.subject or "").strip()
            if text:
                body_parts.append(text)
        body = "\n".join(body_parts) or (ticket.subject or "")

        doc = KnowledgeDocument(
            id=f"ticket-{ticket.id}",
            title=ticket.subject or ticket.id,
            body=body,
            source_type="ticket",
            document_type="case",
            source_id=ticket.id,
            customer=ticket.customer_email,
            tags=[ticket.queue.slug] if ticket.queue and ticket.queue.slug else [],
            metadata={
                "state": ticket.state.value if ticket.state else None,
                "priority": ticket.priority.value if ticket.priority else None,
            },
        )
        self.add_document_with_embedding(doc)
        return doc

    async def ingest_closed_tickets(self, tickets: list[Ticket], *, embed: bool = True) -> int:
        """Ingesta los tickets cerrados/resueltos. Devuelve nº de nuevos documentos."""
        count = 0
        for ticket in tickets:
            if ticket.state in _CLOSED_STATES and self.ingest_ticket(ticket) is not None:
                count += 1
        if embed and count:
            try:
                await self.embed_all_documents()
            except Exception:  # noqa: BLE001 — embeddings best-effort
                pass
        return count

    async def embed_all_documents(self) -> int:
        """Generate embeddings for all documents that don't have one yet."""
        if not self._llm_client:
            return 0

        count = 0
        for doc in self._documents:
            if doc.id in self._vector_store._vectors:
                continue  # Already indexed

            text = f"{doc.title}\n{doc.body}"
            embedding = await self._llm_client.generate_embedding(text)
            self._vector_store.add(doc.id, embedding)
            count += 1

        self._embeddings_done = True
        return count

    async def search_rag(
        self,
        request: KnowledgeSearchRequest,
        *,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> KnowledgeSearchResponse:
        """Hybrid search: keyword + semantic (embedding) with reranking.

        Args:
            semantic_weight: Weight for embedding-based similarity (0-1)
            keyword_weight: Weight for keyword-based score (0-1)

        Returns:
            Reranked search results combining both signals.
        """
        if not self._llm_client or not request.query:
            # Fall back to keyword-only search
            return self.search(request)

        # Ensure embeddings are generated
        if not self._embeddings_done:
            await self.embed_all_documents()

        # 1. Get keyword results
        keyword_results = self._rank_documents(request.query, request)
        keyword_map = {r.document.id: r.score for r in keyword_results}

        # 2. Get embedding
        query_embedding = await self._llm_client.generate_embedding(request.query)

        # 3. Get semantic results from vector store (only for indexed docs)
        semantic_results = self._vector_store.search(
            query_embedding,
            limit=request.limit * 3,
            threshold=0.1,
        )
        semantic_map = {doc_id: score for doc_id, score in semantic_results}

        # 4. Hybrid reranking
        all_ids = set(keyword_map.keys()) | set(semantic_map.keys())

        # Normalize scores to 0-1 range for fair combination
        kw_max = max(keyword_map.values()) if keyword_map else 1.0
        sem_max = max(semantic_map.values()) if semantic_map else 1.0

        combined: list[tuple[str, float, list[str]]] = []
        doc_lookup = {d.id: d for d in self._documents}

        for doc_id in all_ids:
            doc = doc_lookup.get(doc_id)
            if not doc:
                continue

            kw_score = keyword_map.get(doc_id, 0.0) / kw_max
            sem_score = semantic_map.get(doc_id, 0.0) / sem_max if sem_max > 0 else 0.0

            hybrid = (kw_score * keyword_weight) + (sem_score * semantic_weight)

            # Find matched terms from keyword search
            matched: list[str] = []
            kw_result = next(
                (r for r in keyword_results if r.document.id == doc_id), None
            )
            if kw_result:
                matched = kw_result.matched_terms

            combined.append((doc_id, hybrid, matched))

        # 5. Sort by hybrid score
        combined.sort(key=lambda x: (-x[1], x[0]))
        top = combined[: request.limit]

        # 6. Build response
        doc_map = {d.id: d for d in self._documents}
        items = []
        for doc_id, score, matched in top:
            doc = doc_map.get(doc_id)
            if not doc:
                continue
            items.append(KnowledgeSearchResult(
                document=doc,
                score=round(score, 3),
                matched_terms=matched,
                explanation=(
                    f"hybrid(keyword={keyword_weight},semantic={semantic_weight})"
                ),
            ))

        return KnowledgeSearchResponse(
            query=request.query, total=len(items), items=items
        )

    def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        scored = self._rank_documents(request.query, request)
        items = [
            KnowledgeSearchResult(
                document=score.document,
                score=round(score.score, 3),
                matched_terms=score.matched_terms,
                explanation=score.explanation,
            )
            for score in scored[: request.limit]
        ]
        return KnowledgeSearchResponse(query=request.query, total=len(scored), items=items)

    def similar_cases(self, request: SimilarCaseRequest) -> SimilarCasesResponse:
        query = _safe_join([request.subject, request.body_text])
        search_request = KnowledgeSearchRequest(
            query=query,
            limit=request.limit,
            customer=request.customer,
            document_type="case",
            tags=request.tags,
        )
        result = self.search(search_request)
        return SimilarCasesResponse(subject=request.subject, total=result.total, items=result.items)

    def _rank_documents(
        self,
        query: str,
        request: KnowledgeSearchRequest,
    ) -> list[_DocumentScore]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        ranked: list[_DocumentScore] = []
        query_counter = Counter(query_tokens)
        query_term_set = set(query_tokens)
        for document in self._documents:
            if request.document_type and document.document_type != request.document_type:
                continue
            if request.source_type and document.source_type != request.source_type:
                continue
            if request.customer and (document.customer or "").lower() != request.customer.lower():
                continue
            if request.tags:
                doc_tags = {tag.lower() for tag in document.tags}
                if not set(tag.lower() for tag in request.tags).issubset(doc_tags):
                    continue

            title_tokens = Counter(_tokenize(document.title))
            body_tokens = Counter(_tokenize(document.body))
            tag_tokens = Counter(_tokenize(" ".join(document.tags)))
            customer_tokens = Counter(_tokenize(document.customer or ""))
            metadata_tokens = Counter(_tokenize(" ".join(str(value) for value in document.metadata.values())))

            matched_terms = sorted(
                ((query_term_set & set(title_tokens))
                | (query_term_set & set(body_tokens))
                | (query_term_set & set(tag_tokens))
                | (query_term_set & set(customer_tokens))
                | (query_term_set & set(metadata_tokens)))
            )

            title_hits = sum(min(query_counter[token], title_tokens[token]) for token in query_term_set)
            body_hits = sum(min(query_counter[token], body_tokens[token]) for token in query_term_set)
            tag_hits = sum(min(query_counter[token], tag_tokens[token]) for token in query_term_set)
            customer_hits = sum(min(query_counter[token], customer_tokens[token]) for token in query_term_set)
            metadata_hits = sum(min(query_counter[token], metadata_tokens[token]) for token in query_term_set)

            phrase_bonus = 0.0
            lowered_query = query.lower()
            if lowered_query and lowered_query in document.title.lower():
                phrase_bonus += 3.5
            if lowered_query and lowered_query in document.body.lower():
                phrase_bonus += 1.5

            score = (
                title_hits * 4.0
                + body_hits * 1.5
                + tag_hits * 2.5
                + customer_hits * 3.0
                + metadata_hits * 1.0
                + phrase_bonus
            )
            if score <= 0:
                continue

            explanation = (
                f"title={title_hits}, body={body_hits}, tags={tag_hits}, "
                f"customer={customer_hits}, metadata={metadata_hits}, phrase={phrase_bonus:.1f}"
            )
            ranked.append(_DocumentScore(document=document, score=score, matched_terms=matched_terms, explanation=explanation))

        ranked.sort(key=lambda item: (-item.score, item.document.title.lower(), item.document.id))
        return ranked
