"""
RuleClassifierAgent — sub-agente de clasificación basado en reglas de keywords.

Vota usando palabras clave con pesos individuales (1-4).
Es el más rápido (~1ms), no requiere modelo ni red.
Se usa como primer voto en el sistema de votación del orquestador.
"""

import logging
from src.agents.classifier.base import BaseClassifierAgent
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

# Cada keyword tiene: (texto, peso, categoría)
# Peso: 1=genérico, 2=normal, 3=fuerte, 4=muy fuerte
KEYWORD_WEIGHTS: list[tuple[str, int, str]] = [
    # ── Cliente: facturación (2) ──
    ("factura", 2, "cliente"),
    ("invoice", 2, "cliente"),
    ("pago", 2, "cliente"),
    ("payment", 2, "cliente"),
    ("recibo", 2, "cliente"),
    ("receipt", 2, "cliente"),
    # ── Cliente: soporte (2-3) ──
    ("soporte", 2, "cliente"),
    ("support", 2, "cliente"),
    ("incidente", 3, "cliente"),
    ("bug", 3, "cliente"),
    ("error", 2, "cliente"),
    ("problema", 2, "cliente"),
    ("urgente", 2, "cliente"),
    ("fallo", 2, "cliente"),
    # ── Cliente: reuniones (1-2) ──
    ("reunión", 2, "cliente"),
    ("reunion", 2, "cliente"),
    ("meeting", 2, "cliente"),
    ("meet", 1, "cliente"),
    ("schedule", 1, "cliente"),
    ("agendar", 1, "cliente"),
    ("follow-up", 2, "cliente"),
    # ── Cliente: genéricos (1 — no desempatan solos) ──
    ("gracias", 1, "cliente"),
    ("thanks", 1, "cliente"),
    ("ayuda", 1, "cliente"),
    ("help", 1, "cliente"),
    # ── Lead: consultas comerciales (2-3) ──
    ("presupuesto", 3, "lead"),
    ("budget", 3, "lead"),
    ("cotización", 3, "lead"),
    ("quot", 2, "lead"),
    ("quote", 2, "lead"),
    ("precio", 2, "lead"),
    ("costo", 2, "lead"),
    ("cost", 2, "lead"),
    ("price", 2, "lead"),
    ("colaboración", 2, "lead"),
    ("partner", 2, "lead"),
    ("collaboration", 2, "lead"),
    ("partnership", 2, "lead"),
    # ── Proveedor: compras y suministros (2-4) ──
    ("orden de compra", 4, "proveedor"),
    ("proveedor", 3, "proveedor"),
    ("supplier", 3, "proveedor"),
    ("vendor", 3, "proveedor"),
    ("pedido", 3, "proveedor"),
    ("order", 2, "proveedor"),
    ("compra", 2, "proveedor"),
    ("purchase", 2, "proveedor"),
    ("materiales", 3, "proveedor"),
    ("suministro", 3, "proveedor"),
    # ── Proveedor: outreach comercial (1-3) ──
    ("ofertamos", 3, "proveedor"),
    ("ofrecemos", 2, "proveedor"),
    ("distribuidor", 2, "proveedor"),
    ("suministrar", 3, "proveedor"),
    ("fabricante", 2, "proveedor"),
    # ── Proveedor: colaboración (1, baja para no chocar con lead) ──
    ("representante", 1, "proveedor"),
    ("propuesta comercial", 2, "proveedor"),
    # ── Spam/Nulo ──
    ("newsletter", 2, "nulo"),
    ("boletín", 2, "nulo"),
    ("publicidad", 2, "nulo"),
    ("marketing", 1, "nulo"),
    ("suscríbete", 2, "nulo"),
    ("subscribe", 2, "nulo"),
    ("no-reply", 1, "nulo"),
    ("noreply", 1, "nulo"),
]

# Prioridad de categoría para desempate (en contexto B2B)
CATEGORY_PRIORITY: dict[str, int] = {
    "proveedor": 3,
    "lead": 2,
    "cliente": 1,
    "nulo": 0,
}


class RuleClassifierAgent(BaseClassifierAgent):
    """Clasificador por reglas de keywords con votación."""

    @property
    def agent_name(self) -> str:
        return "rule_engine"

    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """Clasifica por keywords y retorna un voto."""
        text = f"{subject or ''} {body or ''}".lower()
        scores: dict[str, float] = {}

        for keyword, weight, category in KEYWORD_WEIGHTS:
            if keyword in text:
                scores[category] = scores.get(category, 0) + weight

        if not scores:
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.3,
                reason="ninguna keyword relevante encontrada",
                details={"scores": {}},
            )

        # Encontrar score máximo
        max_score = max(scores.values())

        # Categorías empatadas
        tied = [cat for cat, sc in scores.items() if sc == max_score]

        if len(tied) == 1:
            winner = tied[0]
            # Normalizar confianza: max_score / 10 (un score de ~7+ es alta confianza)
            confidence = min(0.5 + (max_score * 0.05), 0.85)
            return ClassifierVote(
                agent_name=self.agent_name,
                category=winner,
                confidence=round(confidence, 2),
                reason=f"keyword match: {max_score} pts para '{winner}'",
                details={"scores": scores, "max_score": max_score},
            )

        # Desempate por prioridad de categoría
        tied.sort(key=lambda c: CATEGORY_PRIORITY.get(c, 0), reverse=True)
        winner = tied[0]
        logger.info(
            "RuleEngine empate entre %s → gana %s (prioridad %d)",
            tied,
            winner,
            CATEGORY_PRIORITY.get(winner, 0),
        )
        return ClassifierVote(
            agent_name=self.agent_name,
            category=winner,
            confidence=0.6,
            reason=f"desempate por prioridad entre {tied}",
            details={"scores": scores, "tied": tied, "tiebreak": "priority"},
        )
