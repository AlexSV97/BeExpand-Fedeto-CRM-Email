"""KnowledgeAnswerService — KV-06.

Respuesta RAG fundamentada con **citas obligatorias**: recupera del Knowledge
Vault (search_rag), genera una respuesta basada SOLO en esas fuentes citando
`[n]` vía ``LLMClient``, y cae a un resumen extractivo determinista (con citas)
si no hay backend LLM. Nunca inventa fuentes: las `sources` son siempre los
documentos recuperados.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.llm_client import LLMClient
from src.services.knowledge_vault import KnowledgeSearchRequest, KnowledgeVaultService

logger = logging.getLogger(__name__)

_PROMPT = """Eres un asistente del SOC. Responde la PREGUNTA usando ÚNICAMENTE las FUENTES.
Cita las fuentes relevantes con [n]. Si las fuentes no cubren la pregunta, dilo claramente.
Responde en español, conciso.

PREGUNTA: {query}

FUENTES:
{sources}

Respuesta (con citas [n]):"""


class AnswerSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: int
    id: str
    title: str
    excerpt: str
    score: float = 0.0


class KnowledgeAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    limit: int = 4


class KnowledgeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    answer: str
    sources: list[AnswerSource]
    source: Literal["ai", "extractive", "none"]
    grounded: bool


def _excerpt(body: str | None, n: int = 240) -> str:
    text = (body or "").strip().replace("\n", " ")
    return text[:n]


class KnowledgeAnswerService:
    def __init__(self, vault: KnowledgeVaultService, llm_client: LLMClient | None = None) -> None:
        self._vault = vault
        self._llm = llm_client

    async def answer(self, query: str, limit: int = 4) -> KnowledgeAnswer:
        """Devuelve una respuesta fundamentada con citas. Nunca lanza."""
        try:
            results = await self._vault.search_rag(KnowledgeSearchRequest(query=query, limit=limit))
            items = results.items
        except Exception as exc:  # noqa: BLE001 — recuperación best-effort
            logger.warning("KnowledgeAnswer: search_rag falló (%s)", exc)
            items = []

        if not items:
            return KnowledgeAnswer(
                query=query,
                answer="No encontré información en la base de conocimiento para esa consulta.",
                sources=[],
                source="none",
                grounded=False,
            )

        sources = [
            AnswerSource(
                ref=i + 1,
                id=item.document.id,
                title=item.document.title,
                excerpt=_excerpt(item.document.body),
                score=getattr(item, "score", 0.0) or 0.0,
            )
            for i, item in enumerate(items)
        ]

        ai = await self._answer_ai(query, sources)
        if ai is not None:
            return KnowledgeAnswer(query=query, answer=ai, sources=sources, source="ai", grounded=True)

        return KnowledgeAnswer(
            query=query,
            answer=self._answer_extractive(sources),
            sources=sources,
            source="extractive",
            grounded=True,
        )

    async def _answer_ai(self, query: str, sources: list[AnswerSource]) -> str | None:
        try:
            client = self._llm or LLMClient(use_chat_model=True)
            rendered = "\n".join(f"[{s.ref}] {s.title}: {s.excerpt}" for s in sources)
            prompt = _PROMPT.format(query=query[:300], sources=rendered)
            text = (await client.generate(prompt=prompt, temperature=0.2, max_tokens=400)).strip()
            return text or None
        except Exception as exc:  # noqa: BLE001 — degradar a extractivo
            logger.warning("KnowledgeAnswer: fallo IA (%s); usando extractivo", exc)
            return None

    @staticmethod
    def _answer_extractive(sources: list[AnswerSource]) -> str:
        lines = ["Según la base de conocimiento:"]
        for s in sources[:3]:
            lines.append(f"- {s.excerpt} [{s.ref}]")
        return "\n".join(lines)
