"""
RouterAgent — determina a qué departamento(s) y persona(s) debe ir el email.

Usa un enfoque híbrido:
1. Primero aplica reglas de enrutamiento por keywords (rápido, determinista)
2. Si las reglas no son suficientes, consulta al LLM (Ollama) para decisión contextual

El resultado se usa en el Action Executor para reenviar el email.
"""

import json
import logging
import time

import httpx

from src.config import get_settings
from src.orchestrator.context import (
    ExtractedInfo,
    RoutingDecision,
    EmailData,
)

logger = logging.getLogger(__name__)

# ── Reglas de enrutamiento por departamento ──
# Cada entrada: (keyword, departamento, peso)
ROUTING_RULES: list[tuple[str, str, int]] = [
    # Contabilidad
    ("factura", "contabilidad", 3),
    ("invoice", "contabilidad", 3),
    ("pago", "contabilidad", 3),
    ("payment", "contabilidad", 3),
    ("recibo", "contabilidad", 2),
    ("receipt", "contabilidad", 2),
    ("impuesto", "contabilidad", 2),
    ("iva", "contabilidad", 2),
    ("vencimiento", "contabilidad", 2),
    ("cobro", "contabilidad", 2),
    # Soporte técnico
    ("soporte", "soporte", 3),
    ("support", "soporte", 3),
    ("incidente", "soporte", 3),
    ("bug", "soporte", 3),
    ("error", "soporte", 2),
    ("problema técnico", "soporte", 3),
    ("fallo", "soporte", 2),
    ("ayuda técnica", "soporte", 2),
    ("no funciona", "soporte", 2),
    # Comercial / Ventas
    ("presupuesto", "comercial", 3),
    ("budget", "comercial", 3),
    ("cotización", "comercial", 3),
    ("precio", "comercial", 2),
    ("quiero contratar", "comercial", 3),
    ("colaboración", "comercial", 2),
    ("partner", "comercial", 2),
    ("reunión comercial", "comercial", 2),
    ("propuesta", "comercial", 2),
    # Proveedores / Compras
    ("orden de compra", "proveedores", 3),
    ("pedido", "proveedores", 3),
    ("order", "proveedores", 2),
    ("materiales", "proveedores", 3),
    ("suministro", "proveedores", 3),
    ("almacén", "proveedores", 2),
    ("stock", "proveedores", 2),
    # Dirección
    ("estrategia", "direccion", 2),
    ("reunión directiva", "direccion", 2),
    ("informe trimestral", "direccion", 2),
    ("resultados", "direccion", 2),
]

# Mapeo de categoría → departamento por defecto
CATEGORY_DEFAULT_ROUTE: dict[str, str] = {
    "cliente": "soporte",
    "lead": "comercial",
    "proveedor": "proveedores",
}

ROUTER_PROMPT = """Eres un agente de enrutamiento de correos empresariales. Determina a qué departamento(s) debe ir este email.

DEPARTAMENTOS DISPONIBLES:
- contabilidad: Facturas, pagos, cobros, impuestos, temas financieros
- soporte: Incidencias técnicas, bugs, problemas con el servicio, ayuda técnica
- comercial: Ventas, presupuestos, cotizaciones, nuevos clientes, colaboraciones
- proveedores: Compras, pedidos, proveedores, materiales, suministros
- direccion: Temas estratégicos, informes, reuniones directivas
- otro: Si no encaja claramente en ningún departamento anterior

Analiza tanto el asunto como el cuerpo del email. Ten en cuenta:
1. La categoría del email ({category})
2. La urgencia ({urgency})
3. La acción requerida ({action})
4. El contenido completo

Responde SOLO con un JSON valido SIN markdown:
{{"departments": ["depto1", "depto2"], "persons": [], "rationale": "explicación breve del enrutamiento"}}

Puedes asignar MÚLTIPLES departamentos si el email es relevante para varios.
Si los datos disponibles permiten identificar a una persona concreta, inclúyela en "persons".

Asunto: {subject}
Remitente: {sender_name} <{sender_email}>
Cuerpo: {body}"""


class RouterAgent:
    """Agente que determina el enrutamiento del email a departamentos."""

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_model
        self.url = settings.ollama_url
        self.timeout = settings.ollama_timeout

    async def route(
        self,
        email_data: EmailData,
        extracted: ExtractedInfo | None,
        category: str | None,
    ) -> RoutingDecision:
        """
        Determina el enrutamiento del email.

        Args:
            email_data: Datos crudos del email.
            extracted: Información extraída por el Analyzer (puede ser None).
            category: Categoría final asignada por el clasificador.

        Returns:
            RoutingDecision con departamentos y personas destino.
        """
        # Paso 1: Reglas rápidas
        rule_departments = self._route_by_rules(
            email_data.subject or "",
            email_data.body_plain or "",
            category,
        )

        # Si las reglas dan un resultado claro, lo usamos directamente
        if rule_departments and rule_departments != ["otro"]:
            return RoutingDecision(
                departments=rule_departments,
                persons=[],
                rationale="enrutamiento por reglas de keywords",
                priority=extracted.urgency if extracted else "normal",
            )

        # Paso 2: LLM para casos complejos
        llm_result = await self._route_by_llm(
            subject=email_data.subject or "",
            body=email_data.body_plain or "",
            sender_name=email_data.sender_name,
            sender_email=email_data.sender_email,
            category=category or "sin categoría",
            urgency=extracted.urgency if extracted else "media",
            action=extracted.action_required if extracted else "otro",
        )

        return llm_result

    def _route_by_rules(
        self,
        subject: str,
        body: str,
        category: str | None,
    ) -> list[str]:
        """Enrutamiento rápido por reglas de keywords."""
        text = f"{subject} {body}".lower()
        dept_scores: dict[str, float] = {}

        for keyword, dept, weight in ROUTING_RULES:
            if keyword in text:
                dept_scores[dept] = dept_scores.get(dept, 0) + weight

        if dept_scores:
            max_score = max(dept_scores.values())
            # Solo devolver departamentos con score significativo
            result = sorted(
                [d for d, s in dept_scores.items() if s >= max_score * 0.7],
            )
            if result:
                return result

        # Fallback por categoría
        if category and category in CATEGORY_DEFAULT_ROUTE:
            return [CATEGORY_DEFAULT_ROUTE[category]]

        return ["otro"]

    async def _route_by_llm(
        self,
        subject: str,
        body: str,
        sender_name: str,
        sender_email: str,
        category: str,
        urgency: str,
        action: str,
    ) -> RoutingDecision:
        """Enrutamiento por LLM para casos complejos."""
        start = time.time()

        prompt = ROUTER_PROMPT.format(
            subject=(subject or "")[:200],
            sender_name=(sender_name or "")[:100],
            sender_email=(sender_email or "")[:100],
            body=(body or "")[:3000],
            category=category,
            urgency=urgency,
            action=action,
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

                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()

                result = json.loads(raw)

                elapsed = (time.time() - start) * 1000
                logger.info(
                    "Router LLM: %s -> %s (%.0fms)",
                    subject[:50] if subject else "",
                    result.get("departments", []),
                    elapsed,
                )

                return RoutingDecision(
                    departments=result.get("departments", ["otro"]),
                    persons=result.get("persons", []),
                    rationale=result.get("rationale", ""),
                    priority=urgency,
                )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.warning("Router LLM error: %s", e)
            # Fallback: categoría → departamento por defecto
            default_dept = CATEGORY_DEFAULT_ROUTE.get(category, "otro")
            return RoutingDecision(
                departments=[default_dept],
                persons=[],
                rationale=f"fallback por categoría ({category}) tras error LLM",
                priority=urgency,
            )
