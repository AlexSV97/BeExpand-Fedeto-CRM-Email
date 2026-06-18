"""QueueSuggestionService — CE-02.

Capa de IA sobre la topología de colas (CE-01). Dada una incidencia
(asunto, cuerpo, categoría, urgencia), pide al ``LLMClient`` que elija la mejor
cola de entre las candidatas de la topología viva, con confianza, motivo y
alternativas. Cualquier fallo (sin backend LLM, excepción, JSON inválido o cola
desconocida) degrada de forma determinista a ``QueueStrategyService.recommend()``
(``source="rules"``).
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.ticketing import Queue
from src.llm_client import LLMClient
from src.services.queue_strategy import (
    QueueDecisionRequest,
    QueueStrategyService,
    QueueTier,
    QueueTopologyNode,
)

logger = logging.getLogger(__name__)


SUGGEST_PROMPT = """Eres un enrutador de tickets de soporte. Elige la MEJOR cola para el ticket.

COLAS DISPONIBLES (usa exactamente uno de estos slug):
{candidates}

TICKET:
- Asunto: {subject}
- Categoría: {category}
- Urgencia: {urgency}
- Cuerpo: {body}

Responde SOLO con JSON válido, sin texto adicional, con esta forma exacta:
{{"slug": "<slug de la lista>", "confidence": 0.0-1.0, "reason": "<motivo breve>", "alternatives": ["<slug>", "<slug>"]}}"""


class QueueSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body_text: str
    category: str | None = None
    urgency: str = "media"
    current_tier: QueueTier = QueueTier.N1


class QueueSuggestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue: Queue
    tier: QueueTier
    owner: str
    confidence: float
    reason: str


class QueueSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ai", "rules"]
    recommended: QueueSuggestionItem
    alternatives: list[QueueSuggestionItem] = Field(default_factory=list)
    model: str | None = None


def _clamp_confidence(value: object, default: float = 0.5) -> float:
    try:
        conf = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, conf))


def _extract_json(raw: str) -> dict | None:
    """Extrae el primer objeto JSON de la respuesta del LLM (tolerante)."""
    cleaned = (raw or "").strip()
    if "```" in cleaned:
        # quita fences ```json ... ``` o ``` ... ```
        parts = cleaned.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                cleaned = part
                break
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class QueueSuggestionService:
    def __init__(
        self,
        strategy: QueueStrategyService,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._strategy = strategy
        self._llm = llm_client

    def _candidates(self) -> list[QueueTopologyNode]:
        topology = self._strategy.topology()
        return [*topology.roots, *topology.special_queues]

    async def suggest(self, request: QueueSuggestionRequest) -> QueueSuggestion:
        """Devuelve una sugerencia de cola. Nunca lanza (NFR-3)."""
        try:
            ai = await self._suggest_ai(request)
            if ai is not None:
                return ai
        except Exception as exc:  # noqa: BLE001 — degradar a reglas
            logger.warning("QueueSuggestion: fallo IA (%s); usando reglas", exc)
        return self._suggest_rules(request)

    # ── IA ──────────────────────────────────────────────────────────────
    async def _suggest_ai(self, request: QueueSuggestionRequest) -> QueueSuggestion | None:
        candidates = self._candidates()
        by_slug = {node.queue.slug: node for node in candidates if node.queue.slug}
        if not by_slug:
            return None

        client = self._llm or LLMClient(use_chat_model=True)
        candidate_lines = "\n".join(
            f"- {node.queue.slug} (tier={node.tier.value}, owner={node.owner}): {node.name}"
            for node in candidates
        )
        prompt = SUGGEST_PROMPT.format(
            candidates=candidate_lines,
            subject=(request.subject or "(sin asunto)")[:150],
            category=request.category or "pendiente",
            urgency=request.urgency or "media",
            body=(request.body_text or "")[:1500],
        )

        raw = await client.generate(prompt=prompt, temperature=0.1, max_tokens=200)
        parsed = _extract_json(raw)
        if not parsed:
            return None

        slug = parsed.get("slug")
        node = by_slug.get(slug)
        if node is None:  # REQ-3: cola desconocida → descartar IA
            logger.info("QueueSuggestion: slug '%s' no está en la topología; fallback", slug)
            return None

        recommended = QueueSuggestionItem(
            queue=node.queue,
            tier=node.tier,
            owner=node.owner,
            confidence=_clamp_confidence(parsed.get("confidence"), default=0.7),
            reason=str(parsed.get("reason") or "Sugerido por IA").strip()[:300],
        )

        alternatives: list[QueueSuggestionItem] = []
        for alt_slug in parsed.get("alternatives") or []:
            alt_node = by_slug.get(alt_slug)
            if alt_node is None or alt_slug == slug:
                continue
            alternatives.append(
                QueueSuggestionItem(
                    queue=alt_node.queue,
                    tier=alt_node.tier,
                    owner=alt_node.owner,
                    confidence=max(recommended.confidence - 0.2, 0.1),
                    reason="Alternativa sugerida por IA",
                )
            )

        return QueueSuggestion(
            source="ai",
            recommended=recommended,
            alternatives=alternatives,
            model=getattr(client, "model", None),
        )

    # ── Reglas (fallback determinista) ──────────────────────────────────
    def _suggest_rules(self, request: QueueSuggestionRequest) -> QueueSuggestion:
        decision = self._strategy.recommend(
            QueueDecisionRequest(
                subject=request.subject,
                body_text=request.body_text,
                urgency=request.urgency,
                category=request.category,
                current_tier=request.current_tier,
            )
        )
        routing = decision.routing
        return QueueSuggestion(
            source="rules",
            recommended=QueueSuggestionItem(
                queue=routing.queue,
                tier=routing.tier,
                owner=routing.owner,
                confidence=_clamp_confidence(routing.confidence, default=0.5),
                reason=routing.reason,
            ),
            alternatives=[],
            model=None,
        )
