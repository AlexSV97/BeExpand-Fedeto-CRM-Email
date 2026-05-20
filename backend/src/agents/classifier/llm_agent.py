"""
LLMClassifierAgent — sub-agente de clasificación basado en Ollama (LLM local).

Vota usando análisis semántico profundo con qwen2.5:7b.
Es el más lento (~1-3s) pero el que mejor entiende contexto.
Se usa como voto de referencia en el sistema de votación.
"""

import json
import logging
import re
import time

import httpx

from src.agents.classifier.base import BaseClassifierAgent
from src.config import get_settings
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """Eres un agente de clasificación de correos empresariales. Tu tarea es analizar el email y determinar su categoría.

CATEGORÍAS (elige solo una):
- cliente: El remitente YA ES cliente. Señales: reporta incidencias, pide soporte técnico, habla de facturas de servicio, renovaciones, reuniones de seguimiento, pagos de servicios contratados.
- lead: Potencial cliente (NO es cliente aún). Señales: solicita presupuestos, cotizaciones, información comercial, demos, interés en contratar servicios.
- proveedor: El remitente es un proveedor externo. Señales: ofertas de productos/servicios, facturas de proveedor, actualizaciones de precios, avisos de mantenimiento.
- nulo: Spam, newsletter no solicitado, notificaciones automáticas de sistemas, correos masivos, confirmaciones de plataformas, publicidad no personalizada.

Diferencia clave cliente vs lead: si YA USA tus servicios → cliente. Si está PREGUNTANDO o interesado en contratar → lead.

EJEMPLOS:

Asunto: Incidencia con plataforma de facturación
Cuerpo: Buenos días, desde ayer no podemos acceder al sistema de facturación. Necesitamos que lo revisen urgente. Gracias.
RESPUESTA: {"category": "cliente", "confidence": 0.92, "reason": "Reporta incidencia con servicio que ya usa, tono de urgencia. Cliente existente."}

Asunto: Solicitud de presupuesto servicios consultoría
Cuerpo: Buenos días, nos gustaría recibir información detallada y precios sobre sus servicios de consultoría TI para valorar una posible contratación. Quedamos a la espera.
RESPUESTA: {"category": "lead", "confidence": 0.90, "reason": "Solicita presupuesto sin ser cliente aún, tono consultivo. Potencial cliente."}

Asunto: Oferta especial software gestión empresarial
Cuerpo: Estimados, les escribimos para presentarles nuestra solución de gestión empresarial con descuento por lanzamiento este mes. ¿Les interesa una demo?
RESPUESTA: {"category": "proveedor", "confidence": 0.88, "reason": "Oferta entrante de producto externo no solicitada. Proveedor contactando."}

Asunto: Newsletter semanal de tecnología
Cuerpo: Descubre las últimas novedades en tecnología para tu negocio. Este mes te traemos los mejores consejos para digitalizar tu empresa.
RESPUESTA: {"category": "nulo", "confidence": 0.95, "reason": "Newsletter genérico sin relación comercial directa. Correo masivo."}

Asunto: Reunión de seguimiento proyecto Q2
Cuerpo: Hola, tal como acordamos te envío la agenda para la reunión de seguimiento del próximo martes. Adjunto el informe de avance del proyecto.
RESPUESTA: {"category": "cliente", "confidence": 0.85, "reason": "Reunión de seguimiento con cliente existente. Proyecto en curso."}

Asunto: Consulta sobre precios de planes
Cuerpo: Estoy interesado en sus servicios pero me gustaría saber si tienen planes para pymes. Agradecería me llamaran para comentarlo.
RESPUESTA: {"category": "lead", "confidence": 0.93, "reason": "Consulta comercial sin ser cliente. Potencial lead interesado."}

Reglas IMPORTANTES:
- Si hay dudas entre cliente y lead, prioriza lead (mejor pecar de optimista para no perder oportunidades).
- Si hay dudas entre nulo y cualquier categoría, prioriza la categoría (mejor clasificar que descartar).
- El campo "reason" debe explicar el razonamiento en 1 frase corta.
- La confianza debe reflejar tu seguridad: 0.95+ para casos claros, 0.60-0.75 para dudosos.

Responde ÚNICAMENTE con un JSON válido en este formato exacto, sin markdown, sin explicaciones adicionales:
{"category": "cliente", "confidence": 0.85, "reason": "explicación breve"}

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
            subject=(subject or "")[:250],
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
                        "max_tokens": 256,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data.get("response", "").strip()

                # Extraer JSON robusto: probar parsing directo, luego regex
                result = self._extract_json(raw)

                category = result.get("category", "nulo").lower()
                confidence = float(result.get("confidence", 0.5))
                reason = result.get("reason", "")

                # Validar categoría
                valid_categories = ("cliente", "lead", "proveedor", "nulo")
                if category not in valid_categories:
                    logger.warning(
                        "LLM categoría inválida '%s', forzando nulo. Raw: %s",
                        category, raw[:100],
                    )
                    category = "nulo"

                # Acotar confianza
                confidence = max(0.0, min(1.0, confidence))

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
                    category=category,
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

    def _extract_json(self, raw: str) -> dict:
        """Extrae un dict JSON de la respuesta cruda del LLM, con múltiples estrategias de fallback."""
        if not raw:
            return {"category": "nulo", "confidence": 0.0, "reason": "respuesta vacía del LLM"}

        # ── Estrategia 1: intentar parsear directamente ──
        cleaned = raw.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # ── Estrategia 2: quitar bloques markdown ──
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # ── Estrategia 3: buscar el primer { ... } con regex ──
        brace_match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if brace_match:
            candidate = brace_match.group()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            # ── Estrategia 4: intentar reparar JSON truncado ──
            try:
                # Añadir comillas a keys sin comillas (ej: {category: "cliente"})
                repaired = re.sub(r"(\s+)(\w+)(\s*):", r'\1"\2"\3:', candidate)
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # ── Estrategia 5: extraer category con regex directamente ──
        cat_match = re.search(r'"category"\s*:\s*"(cliente|lead|proveedor|nulo)"', cleaned, re.IGNORECASE)
        conf_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', cleaned)
        reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', cleaned, re.DOTALL)

        result: dict[str, str | float] = {}
        if cat_match:
            result["category"] = cat_match.group(1).lower()
        if conf_match:
            try:
                result["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass
        if reason_match:
            result["reason"] = reason_match.group(1).strip()

        if result:
            result.setdefault("category", "nulo")
            result.setdefault("confidence", 0.5)
            result.setdefault("reason", "extraído por regex")
            return result

        # ── Fallback final ──
        logger.warning("No se pudo extraer JSON del LLM. Raw: %s", raw[:150])
        return {"category": "nulo", "confidence": 0.0, "reason": f"parseo fallido: {raw[:80]}"}
