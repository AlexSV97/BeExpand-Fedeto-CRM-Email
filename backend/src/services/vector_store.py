"""
Simple in-memory vector store with cosine similarity.
No external dependencies — pure Python math.
"""
from __future__ import annotations

import json
import math
from typing import Any


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    """In-memory vector store with cosine similarity search.

    Thread-safe for read operations. Serializes to/from JSON for persistence.
    """

    def __init__(self, dimensions: int = 768):
        self._dimensions = dimensions
        self._vectors: dict[str, list[float]] = {}  # document_id → embedding

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def size(self) -> int:
        return len(self._vectors)

    def add(self, document_id: str, embedding: list[float]) -> None:
        """Add or update a document embedding."""
        self._vectors[document_id] = embedding

    def remove(self, document_id: str) -> None:
        """Remove a document embedding."""
        self._vectors.pop(document_id, None)

    def search(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.0,
    ) -> list[tuple[str, float]]:
        """Return (document_id, similarity_score) sorted by descending score."""
        results: list[tuple[str, float]] = []
        for doc_id, vec in self._vectors.items():
            score = _cosine_similarity(query_embedding, vec)
            if score >= threshold:
                results.append((doc_id, score))
        results.sort(key=lambda x: (-x[1], x[0]))
        return results[:limit]

    def to_json(self) -> str:
        """Serialize to JSON for persistence."""
        return json.dumps({
            "dimensions": self._dimensions,
            "vectors": {k: v for k, v in self._vectors.items()},
        })

    @classmethod
    def from_json(cls, data: str) -> VectorStore:
        """Deserialize from JSON."""
        parsed = json.loads(data)
        store = cls(dimensions=parsed.get("dimensions", 768))
        store._vectors = parsed.get("vectors", {})
        return store
