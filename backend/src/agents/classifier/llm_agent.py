"""
LLMClassifierAgent — sub-agente de clasificación basado en Ollama (LLM local).

Vota usando análisis semántico profundo con qwen2.5:7b.
Es el más lento (~1-3s) pero el que mejor entiende contexto.
Se usa como voto de referencia en el sistema de votación.
"""

import json
import logging
import time

import httpx

from src.agents.classifier.base import BaseClassifierAgent
from src.config import get_settings
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """Eres un agente de clasificación de correos empresariales. Tu tarea es analizar el email y determinar su categoría.

CATEGORÍAS:
- cliente: El remitente ES un cliente existente. Busca facturas, pagos, soporte técnico, reuniones de seguimiento, incidentes, problemas con el servicio.
- lead: Es un potencial cliente. Busca solicitudes de presupuesto, cotizaciones, consultas comerciales, propuestas de colaboración, interés en servicios.
- proveedor: El remitente es un proveedor. Busca órdenes de compra, facturas de proveedor, pedidos de materiales, suministros, ofertas de productos.
- nulo: Spam, newsletter, notificaciones automáticas, correos masivos, o información irrelevante para el negocio.

Analiza el contenido completo, no solo keywords. Ten en cuenta:
- El contexto de la conversación
- La intención del remitente
- La relación comercial implícita

Responde SOLO con un JSON valido SIN markdown:
{{"category": "cliente|lead|proveedor|nulo", "confidence": 0.0-1.0, "reason": "explicación breve del análisis"}}

Asunto: {subject}
Cuerpo: {body}"""


class LLMClassifierAgent(BaseClassifierAgent):
    """Clasificador por LLM (Ollama) que vota en el sistema multi-agente."""

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_model
        self.url = settings.ollama_url
        self.timeout = settings.ollama_timeout

    @property
    def agent_name(self) -> str:
        return "llm"

    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """Clasifica usando Ollama. Retorna un voto."""
        start = time.time()

        prompt = CLASSIFY_PROMPT.format(
            subject=(subject or "")[:200],
            body=(body or "")[:3000],
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.1,
                        "max_tokens": 128,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data.get("response", "").strip()

                # Extraer JSON de la respuesta (quitar markdown si viene)
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()

                result = json.loads(raw)
                category = result.get("category", "nulo").lower()
                confidence = float(result.get("confidence", 0.5))
                reason = result.get("reason", "")

                elapsed = (time.time() - start) * 1000
                logger.info(
                    "LLM votó: %s -> %s (%.0f%%) en %.0fms | razón: %s",
                    subject[:50] if subject else "",
                    category,
                    confidence * 100,
                    elapsed,
                    reason[:80],
                )

                return ClassifierVote(
                    agent_name=self.agent_name,
                    category=category if category in ("cliente", "lead", "proveedor", "nulo") else "nulo",
                    confidence=round(confidence, 2),
                    reason=reason or "análisis LLM",
                    details={
                        "model": self.model,
                        "raw_response": raw,
                        "processing_ms": round(elapsed, 1),
                    },
                )

        except Exception as e:
            logger.warning("LLM classification failed: %s", e)
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=f"error LLM: {e}",
                details={"error": str(e)},
            )
