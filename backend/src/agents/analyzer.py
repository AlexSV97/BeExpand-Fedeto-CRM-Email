"""
AnalyzerAgent — extrae información estructurada del email usando LLM (OpenRouter/Ollama).

Este agente es el primero en ejecutarse. Analiza el email y extrae:
- Empresa del remitente
- Cargo/puesto
- Nivel de urgencia
- Acción requerida
- Entidades clave (fechas, montos, referencias)
- Tono del mensaje
- Resumen ejecutivo (1-2 frases)

El resultado lo usan el Router (para enrutar correctamente) y el
Action Executor (para incluirlo en la notificación del dashboard).
"""

import json
import logging
import time

from src.config import get_settings
from src.llm_client import LLMClient
from src.orchestrator.context import AnalyzerResult, ExtractedInfo

logger = logging.getLogger(__name__)

ANALYZER_PROMPT = """Eres un analista de correos empresariales. Extrae información estructurada del siguiente email.

Analiza el contenido y extrae:

1. company: Nombre de la empresa del remitente (si se puede deducir del dominio email, firma o contenido). Si no, null.
2. position: Cargo del remitente (si se deduce). Si no, null.
3. urgency: Nivel de urgencia del mensaje. "alta" si el ASUNTO o el cuerpo contienen palabras como urgente, inmediato, ASAP, critical, deadline, urgencia. "baja" si es informativo, newsletter, confirmación. "media" en el resto. El asunto es el indicador MÁS importante.
4. action_required: Tipo de acción que requiere el email. Una de: "pago", "soporte", "consulta", "reunion", "compra", "informativo", "otro".
5. action_description: Descripción breve de la acción requerida (1 frase). Si es informativo, null.
6. entities: Objeto con entidades clave encontradas:
   - dates: lista de fechas mencionadas
   - amounts: lista de montos/económicos mencionados
   - references: lista de números de referencia (factura, pedido, etc.)
7. tone: Tono del mensaje. "formal", "informal", "urgente", "cordial".
8. summary: Resumen ejecutivo del email en 1-2 frases en español. Debe capturar: quién escribe, qué solicita/comunica, y próximos pasos si los hay.

Responde SOLO con un JSON valido SIN markdown ni etiquetas:
{{"company": "..." o null, "position": "..." o null, "urgency": "alta|media|baja", "action_required": "pago|soporte|consulta|reunion|compra|informativo|otro", "action_description": "..." o null, "entities": {{"dates": [...], "amounts": [...], "references": [...]}}, "tone": "formal|informal|urgente|cordial", "summary": "..."}}

Asunto: {subject}
Remitente: {sender_name} <{sender_email}>
Cuerpo: {body}"""


class AnalyzerAgent:
    """Agente que extrae información estructurada del email usando LLM."""

    def __init__(self, model: str | None = None, timeout: int | None = None):
        settings = get_settings()
        # Analyzer prompt es más grande → necesita más tiempo
        if timeout:
            timeout_val = timeout
        elif settings.openrouter_api_key:
            timeout_val = settings.openrouter_timeout * 2
        else:
            timeout_val = settings.ollama_timeout or 10
        self._client = LLMClient(model=model, timeout=timeout_val)

    async def analyze(
        self,
        subject: str,
        body: str,
        sender_name: str = "",
        sender_email: str = "",
    ) -> AnalyzerResult:
        """
        Analiza un email y extrae información estructurada.

        Args:
            subject: Asunto del email.
            body: Cuerpo del email.
            sender_name: Nombre del remitente.
            sender_email: Email del remitente.

        Returns:
            AnalyzerResult con extracted info o error.
        """
        start = time.time()

        prompt = ANALYZER_PROMPT.format(
            subject=(subject or "")[:200],
            sender_name=(sender_name or "")[:100],
            sender_email=(sender_email or "")[:100],
            body=(body or "")[:3000],
        )

        try:
            raw = await self._client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=256,
            )

            # Extraer JSON
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)

            # Post-process: override urgente si el asunto contiene palabras clave
            # El LLM pequeño (llama3.2:3b) a veces ignora "URGENTE" en el asunto
            urgency = result.get("urgency", "media")
            subject_lower = (subject or "").lower()
            urgency_keywords = ["urgente", "asap", "inmediato", "critical", "deadline", "urge", "urgent"]
            if any(kw in subject_lower for kw in urgency_keywords):
                if urgency != "alta":
                    logger.info(
                        "Analyzer urgency override: subject='%s' LLM said '%s' → forzado a 'alta'",
                        subject[:50], urgency,
                    )
                urgency = "alta"

            extracted = ExtractedInfo(
                company=result.get("company"),
                position=result.get("position"),
                urgency=urgency,
                action_required=result.get("action_required"),
                action_description=result.get("action_description"),
                entities=result.get("entities", {}),
                tone=result.get("tone"),
                summary=result.get("summary"),
            )

            elapsed = (time.time() - start) * 1000
            logger.info(
                "Analyzer: %s | urgency=%s action=%s (%.0fms)",
                subject[:50] if subject else "",
                extracted.urgency,
                extracted.action_required,
                elapsed,
            )

            return AnalyzerResult(
                success=True,
                extracted=extracted,
                processing_time_ms=round(elapsed, 1),
            )

        except json.JSONDecodeError as e:
            elapsed = (time.time() - start) * 1000
            logger.warning("Analyzer JSON error: %s | raw: %s", e, raw[:100] if raw else "")
            # Fallback: devolver datos mínimos
            return AnalyzerResult(
                success=False,
                extracted=ExtractedInfo(
                    summary="No se pudo analizar el correo automáticamente.",
                ),
                error=f"Error de parseo JSON: {e}",
                processing_time_ms=round(elapsed, 1),
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            err_msg = str(e) or f"{type(e).__name__} (sin mensaje)"
            logger.warning("Analyzer error: %s", err_msg)
            return AnalyzerResult(
                success=False,
                extracted=ExtractedInfo(
                    summary="No se pudo analizar el correo automáticamente.",
                ),
                error=err_msg,
                processing_time_ms=round(elapsed, 1),
            )
