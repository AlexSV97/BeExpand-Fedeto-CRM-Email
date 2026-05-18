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
- cliente: El remitente YA ES cliente. Señales: incidencias, soporte técnico, facturas de servicio, renovaciones, reuniones de seguimiento, pagos.
- lead: Potencial cliente (NO es cliente aún). Señales: solicitudes de presupuesto, cotizaciones, consultas comerciales, interés en servicios.
- proveedor: El remitente es un proveedor externo. Señales: ofertas de productos/servicios, pedidos de compra, facturas de proveedor, suministros.
- nulo: Spam, newsletter, notificaciones automáticas de sistemas, correos masivos, confirmaciones de plataformas.

Diferencia clave cliente vs lead: si YA usa/contrata tus servicios → cliente. Si está preguntando o interesado en contratar → lead.

EJEMPLOS:

Asunto: Incidencia con plataforma de facturación
Cuerpo: Buenos días, desde ayer no podemos acceder al sistema. Necesitamos que lo revisen urgente.
→ {{"category": "cliente", "confidence": 0.92, "reason": "Reporta incidencia con servicio que ya usa, tono de urgencia → cliente existente"}}

Asunto: Solicitud de presupuesto servicios consultoría
Cuerpo: Nos gustaría recibir información y precios sobre sus servicios de consultoría TI.
→ {{"category": "lead", "confidence": 0.88, "reason": "Solicita presupuesto sin ser cliente aún, tono consultivo → potencial cliente"}}

Asunto: Oferta especial software gestión
Cuerpo: Les escribimos para presentarles nuestra solución de gestión empresarial con descuento por lanzamiento.
→ {{"category": "proveedor", "confidence": 0.85, "reason": "Oferta entrante de producto externo no solicitada → proveedor"}}

Asunto: Tu factura mensual de Azure está lista
Cuerpo: Tu factura correspondiente al período marzo 2026 ya está disponible en el portal.
→ {{"category": "nulo", "confidence": 0.95, "reason": "Notificación automática de plataforma cloud, sin interacción humana → nulo"}}

Reglas:
- Si hay dudas entre cliente y lead, prioriza lead (mejor pecar de optimista).
- Si hay dudas entre nulo y cualquier categoría, prioriza la categoría (mejor clasificar que descartar).
- El "reason" debe explicar el razonamiento en 1 frase.

Responde SOLO con un JSON valido SIN markdown:
{{"category": "cliente|lead|proveedor|nulo", "confidence": 0.0-1.0, "reason": "explicación breve del análisis"}}

Asunto: {subject}
Cuerpo: {body}"""


class LLMClassifierAgent(BaseClassifierAgent):
    """Clasificador por LLM (Ollama) que vota en el sistema multi-agente."""

    def __init__(self, model: str | None = None, timeout: int | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_model
        self.url = settings.ollama_url
        # Prompt con few-shot examples necesita más tiempo
        self.timeout = timeout or settings.ollama_timeout * 2

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
            err_msg = str(e) or f"{type(e).__name__} (sin mensaje)"
            logger.warning("LLM classification failed: %s", err_msg)
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=f"error LLM: {err_msg}",
                details={"error": err_msg},
            )
