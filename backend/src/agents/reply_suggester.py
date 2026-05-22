"""
ReplySuggesterAgent — genera un borrador de respuesta contextual para un email.

Se ejecuta tras el Router, antes del ActionExecutor. Usa Ollama para
redactar una respuesta profesional adaptada al contenido del email,
su categoría y la información extraída por el Analyzer.

El borrador se guarda en extra_data["suggested_reply"] del email.
"""

import logging
import time

import httpx

from src.config import get_settings
from src.orchestrator.context import EmailContext, ExtractedInfo

logger = logging.getLogger(__name__)

REPLY_PROMPT = """Eres un asistente comercial que redacta respuestas a correos empresariales.

Genera un BORRADOR DE RESPUESTA profesional para el siguiente correo recibido.

DATOS DEL CORREO:
- Asunto: {subject}
- Remitente: {sender_name} ({sender_email})
- Empresa: {company}
- Categoría: {category}
- Urgencia: {urgency}
- Acción requerida: {action_required}
- Tono del remitente: {tone}
- Resumen del análisis: {summary}

CUERPO DEL CORREO ORIGINAL:
{body}

INSTRUCCIONES:
1. Redacta un borrador de respuesta en español, profesional y directo.
2. Adapta el tono al del remitente (si es formal, responde formal; si es cordial, cordial).
3. Si el correo solicita algo concreto (presupuesto, reunión, soporte), acúsalo y propón próximos pasos.
4. Si es un lead nuevo, preséntate brevemente y ofrece ayuda.
5. Si es un cliente existente, dirígete por su nombre y refiere la relación existente.
6. Incluye un saludo inicial ({saludo}) y un cierre cordial.
7. NO uses placeholders como [nombre] o [empresa] — usa los datos reales proporcionados.
8. Extensión: 3-5 párrafos máximo.
9. NO incluyas "Asunto:" ni líneas de encabezado — solo el cuerpo del correo.

Responde SOLO con el borrador, sin explicaciones adicionales."""


class ReplySuggesterAgent:
    """Genera borradores de respuesta contextual usando Ollama.

    Usa el modelo de chat (qwen2.5:3b / phi4-mini) porque:
    - Es más rápido en CPU
    - Ya está caliente en memoria (keep_alive desde chat_service)
    - Es un modelo conversacional, ideal para generar borradores
    """

    def __init__(self, model: str | None = None, timeout: int | None = None):
        settings = get_settings()
        self.model = model or settings.chat_model
        self.url = settings.ollama_url
        self.timeout = timeout or settings.chat_timeout

    async def generate(
        self,
        ctx: EmailContext,
    ) -> str:
        """
        Genera un borrador de respuesta para el email en el contexto.

        Args:
            ctx: EmailContext completo con análisis, categoría y extracción.

        Returns:
            Borrador de respuesta en texto plano, o cadena vacía si falla.
        """
        start = time.time()
        extracted = ctx.extracted or ExtractedInfo()

        # Seleccionar saludo según el nombre del remitente
        sender_name = ctx.raw.sender_name or ctx.raw.sender_email.split("@")[0]
        name_part = sender_name.split()[0] if sender_name else ""
        saludo = f"Estimado/a {name_part}," if name_part else "Estimado/a,"

        # Truncar cuerpo para no exceder tokens
        body = (ctx.raw.body_plain or "")[:2000]

        prompt = REPLY_PROMPT.format(
            subject=(ctx.raw.subject or "(sin asunto)")[:150],
            sender_name=sender_name[:80],
            sender_email=(ctx.raw.sender_email or "")[:80],
            company=(extracted.company or "no identificada")[:80],
            category=ctx.final_category or "pendiente",
            urgency=extracted.urgency or "media",
            action_required=extracted.action_required or "ninguna",
            tone=extracted.tone or "neutral",
            summary=(extracted.summary or "Sin resumen disponible")[:300],
            body=body,
            saludo=saludo,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.3,
                        "max_tokens": 512,
                        "keep_alive": -1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data.get("response", "").strip()

            elapsed = (time.time() - start) * 1000
            logger.info(
                "ReplySuggester: %s | %d chars (%.0fms)",
                ctx.raw.subject[:50] if ctx.raw.subject else "",
                len(reply),
                elapsed,
            )
            return reply

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.warning(
                "ReplySuggester error conv=%s: %s (%.0fms)",
                ctx.raw.subject[:30] if ctx.raw.subject else "",
                e,
                elapsed,
            )
            return ""
