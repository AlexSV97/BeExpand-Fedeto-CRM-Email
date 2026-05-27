"""
VoteResolver — resuelve los votos de los sub-agentes del clasificador.

Estrategias de resolución:
1. CONSENSUS: Los 3 agentes coinciden en la misma categoría → se acepta con confianza media
2. MAJORITY: 2 de 3 coinciden → se acepta con confianza media
3. LLM_JUDGE: Los 3 dan categorías distintas → el LLM juzga viendo los votos + el análisis
4. FALLBACK: Si todo falla → nulo con confianza baja
"""

import json
import logging

from src.config import get_settings
from src.llm_client import LLMClient
from src.orchestrator.context import ClassifierVote, EmailContext

logger = logging.getLogger(__name__)

# Umbrales de confianza por agente para considerar un voto válido
MIN_CONFIDENCE: dict[str, float] = {
    "rule_engine": 0.4,
    "bert": 0.5,
    "llm": 0.5,
}

JUDGE_PROMPT = """Eres un juez de clasificación de correos empresariales. Debes decidir la categoría final.

Un sistema multi-agente ha analizado el email y no hay consenso entre los agentes.

VOTOS DE LOS AGENTES:
{votes}

INFORMACIÓN ADICIONAL DEL ANÁLISIS:
- Urgencia: {urgency}
- Acción requerida: {action}
- Empresa detectada: {company}
- Resumen: {summary}

EMAIL:
Asunto: {subject}
Remitente: {sender_name} <{sender_email}>
Cuerpo: {body}

Tu tarea es decidir la categoría final. Analiza los votos, la información disponible y el contenido del email.

CATEGORÍAS:
- cliente: El remitente ES un cliente existente. Facturas, pagos, soporte, reuniones.
- lead: Es un potencial cliente. Presupuestos, cotizaciones, consultas comerciales.
- proveedor: El remitente es un proveedor. Órdenes de compra, pedidos, suministros.
- nulo: Spam, newsletter, notificaciones, o irrelevante.

Responde SOLO con un JSON valido SIN markdown:
{{"category": "cliente|lead|proveedor|nulo", "confidence": 0.0-1.0, "reasoning": "explicación del razonamiento"}}"""


class VoteResolver:
    """Resuelve los votos de los sub-agentes del clasificador."""

    def __init__(self, model: str | None = None):
        self._client = LLMClient(model=model, use_chat_model=True)

    async def resolve(self, ctx: EmailContext) -> tuple[str, float, str]:
        """
        Resuelve los votos y determina la categoría final.

        Args:
            ctx: EmailContext con votes[] poblado por los sub-agentes.

        Returns:
            (categoría_final, confianza_final, método_de_resolución)
        """
        if not ctx.votes:
            logger.warning("No hay votos — devolviendo nulo")
            return "nulo", 0.0, "fallback"

        # Filtrar votos válidos (por encima del umbral de confianza)
        valid_votes = [
            v for v in ctx.votes
            if v.confidence >= MIN_CONFIDENCE.get(v.agent_name, 0.0)
        ]

        if not valid_votes:
            # Si ningún voto supera el umbral, intentar con el mejor
            best = max(ctx.votes, key=lambda v: v.confidence)
            if best.confidence >= 0.3:
                return best.category, best.confidence, "fallback"
            return "nulo", 0.0, "fallback"

        # 1. CONSENSUS: todos los votos válidos coinciden
        categories = [v.category for v in valid_votes]
        if len(set(categories)) == 1:
            avg_conf = sum(v.confidence for v in valid_votes) / len(valid_votes)
            logger.info(
                "CONSENSUS: %s (%.0f%%) entre %d agente(s)",
                categories[0],
                avg_conf * 100,
                len(valid_votes),
            )
            return categories[0], round(avg_conf, 2), "consensus"

        # 2. MAJORITY: 2 de 3 coinciden (o 2+ coinciden)
        from collections import Counter
        counter = Counter(categories)
        top_cat, top_count = counter.most_common(1)[0]

        if top_count >= 2:
            # Confianza = media de los que votaron la mayoría
            majority_votes = [v for v in valid_votes if v.category == top_cat]
            avg_conf = sum(v.confidence for v in majority_votes) / len(majority_votes)
            logger.info(
                "MAJORITY: %s (%.0f%%) — %d de %d agentes",
                top_cat,
                avg_conf * 100,
                top_count,
                len(valid_votes),
            )
            return top_cat, round(avg_conf, 2), "majority"

        # 3. LLM_JUDGE: sin consenso, el LLM decide
        logger.info(
            "Sin consenso entre %d agentes — consultando juez LLM",
            len(valid_votes),
        )
        return await self._judge_by_llm(ctx)

    async def _judge_by_llm(self, ctx: EmailContext) -> tuple[str, float, str]:
        """Usa el LLM como juez para decidir la categoría final."""
        # Preparar votos para el prompt
        votes_text = "\n".join([
            f"- {v.agent_name}: '{v.category}' (confianza: {v.confidence:.0%}) — {v.reason or ''}"
            for v in ctx.votes
        ])

        prompt = JUDGE_PROMPT.format(
            votes=votes_text,
            urgency=ctx.extracted.urgency if ctx.extracted else "desconocida",
            action=ctx.extracted.action_required if ctx.extracted else "desconocida",
            company=ctx.extracted.company if ctx.extracted else "no detectada",
            summary=ctx.extracted.summary if ctx.extracted else "no disponible",
            subject=(ctx.raw.subject or "")[:200],
            sender_name=(ctx.raw.sender_name or "")[:100],
            sender_email=(ctx.raw.sender_email or "")[:100],
            body=(ctx.raw.body_plain or "")[:2000],
        )

        try:
            raw = await self._client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=256,
            )

            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            category = result.get("category", "nulo").lower()
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "")

            logger.info(
                "LLM_JUDGE: %s (%.0f%%) — %s",
                category,
                confidence * 100,
                reasoning[:100],
            )

            if category not in ("cliente", "lead", "proveedor", "nulo"):
                category = "nulo"

            return category, round(confidence, 2), "llm_judge"

        except Exception as e:
            logger.warning("Juez LLM falló: %s → fallback a mejor voto", e)
            # Fallback: mejor voto individual
            best = max(ctx.votes, key=lambda v: v.confidence)
            return best.category, best.confidence, "fallback"
