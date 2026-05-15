"""
Generador de resúmenes de correos usando Ollama (LLM local).

Se ejecuta después de la clasificación para producir un resumen conciso
que ayude a:

- Visualizar rápidamente el contenido del email en el dashboard
- Mejorar la precisión del clasificador (resumen como feature adicional)
- Sentar las bases para el enrutamiento inteligente (Fase 2)

Uso:
    from src.email_processor.summarizer import generate_summary
    resumen = await generate_summary("asunto", "cuerpo del email")
"""

import json
import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """Eres un asistente que resume correos empresariales de forma concisa.
Genera un resumen en español de 1-2 frases que capture:
- Quién es el remitente (si se deduce del contexto)
- Qué solicita o comunica
- Próximos pasos o acciones requeridas (si las hay)

Responde SOLO con un JSON valido:
{{"summary": "resumen en 1-2 frases", "action_required": true|false, "action_description": "descripcion de la accion si aplica"}}

Asunto: {subject}
Cuerpo: {body}"""


async def generate_summary(subject: str, body: str) -> dict:
    """
    Genera un resumen de un correo usando Ollama.

    Args:
        subject: Asunto del correo.
        body: Cuerpo del correo en texto plano.

    Returns:
        dict con:
        - summary: str — resumen en 1-2 frases (o mensaje de error)
        - action_required: bool — si requiere alguna acción
        - action_description: str — descripción de la acción (vacío si no aplica)
    """
    if not subject and not body:
        return {
            "summary": "Correo vacío o sin contenido.",
            "action_required": False,
            "action_description": "",
        }

    settings = get_settings()

    # Limitar tamaño del cuerpo para no saturar el prompt
    truncated_body = (body or "")[:2000]
    truncated_subject = (subject or "")[:200]

    prompt = SUMMARY_PROMPT.format(
        subject=truncated_subject,
        body=truncated_body,
    )

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,
                    "max_tokens": 256,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()

            # Extraer JSON de la respuesta (puede venir con markdown)
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)
            summary = result.get("summary", "")
            action_required = result.get("action_required", False)
            action_description = result.get("action_description", "")

            logger.info(
                "Resumen generado (%d chars) | acción=%s",
                len(summary),
                action_required,
            )
            return {
                "summary": summary,
                "action_required": action_required,
                "action_description": action_description,
            }

    except Exception as e:
        logger.warning("Error generando resumen con Ollama: %s", e)
        return {
            "summary": "No se pudo generar el resumen automático.",
            "action_required": False,
            "action_description": "",
        }
