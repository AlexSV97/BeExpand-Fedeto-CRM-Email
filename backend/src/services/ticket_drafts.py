"""TicketDraftService — CP-05 / CP-06.

Genera borradores asistidos por IA para un ticket: respuesta al cliente (CP-05) y
nota interna accionable (CP-06). Usa ``LLMClient`` con fallback determinista a
plantilla cuando no hay backend LLM (política free-tier + reglas). Los borradores
SIEMPRE requieren aprobación humana antes de enviarse (CP-07): este servicio solo
los redacta, nunca los envía.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.domain.ticketing import Ticket
from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

DraftKind = Literal["customer_reply", "internal_note"]

_CUSTOMER_PROMPT = """Eres un agente de soporte. Redacta un BORRADOR de respuesta al cliente para este ticket.

Ticket: {subject}
Cliente: {customer}
Contexto (últimos mensajes):
{context}

Instrucciones: español, profesional y directo; acusa el problema y propón próximos pasos; 2-4 párrafos; sin placeholders. Responde SOLO con el cuerpo del mensaje."""

_INTERNAL_PROMPT = """Eres un agente de soporte. Redacta una NOTA INTERNA accionable (no visible al cliente) para este ticket.

Ticket: {subject}
Contexto (últimos mensajes):
{context}

Instrucciones: español, conciso, orientado a acción (qué se sabe, hipótesis, próximos pasos, a quién escalar si procede); bullets si ayuda. Responde SOLO con la nota."""


class DraftResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    kind: DraftKind
    source: Literal["ai", "template"]
    text: str
    requires_approval: bool = True
    model: str | None = None


class TicketDraftService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client

    @staticmethod
    def _context(ticket: Ticket, max_articles: int = 4) -> str:
        articles = ticket.articles[-max_articles:] if ticket.articles else []
        lines = []
        for a in articles:
            who = a.author_name or (a.author_kind.value if a.author_kind else "?")
            body = (a.body_text or a.subject or "").strip().replace("\n", " ")
            if body:
                lines.append(f"- {who}: {body[:300]}")
        return "\n".join(lines) or "(sin mensajes previos)"

    async def draft(self, ticket: Ticket, kind: DraftKind) -> DraftResult:
        """Genera un borrador. Nunca lanza: cae a plantilla ante cualquier fallo."""
        context = self._context(ticket)
        try:
            client = self._llm or LLMClient(use_chat_model=True)
            prompt_tpl = _CUSTOMER_PROMPT if kind == "customer_reply" else _INTERNAL_PROMPT
            prompt = prompt_tpl.format(
                subject=(ticket.subject or "(sin asunto)")[:200],
                customer=ticket.customer_email or "cliente",
                context=context,
            )
            text = (await client.generate(prompt=prompt, temperature=0.3, max_tokens=512)).strip()
            if text:
                return DraftResult(
                    ticket_id=ticket.id,
                    kind=kind,
                    source="ai",
                    text=text,
                    model=getattr(client, "model", None),
                )
        except Exception as exc:  # noqa: BLE001 — degradar a plantilla
            logger.warning("TicketDraft: fallo IA (%s); usando plantilla", exc)

        return DraftResult(
            ticket_id=ticket.id,
            kind=kind,
            source="template",
            text=self._template(ticket, kind),
        )

    @staticmethod
    def _template(ticket: Ticket, kind: DraftKind) -> str:
        subject = ticket.subject or "su solicitud"
        if kind == "customer_reply":
            return (
                f"Estimado/a,\n\n"
                f"Hemos recibido su solicitud relacionada con \"{subject}\" y ya estamos "
                f"trabajando en ella. Le mantendremos informado/a de los avances y le "
                f"contactaremos en cuanto tengamos una actualización.\n\n"
                f"Gracias por su paciencia.\nUn saludo,\nEquipo de Soporte"
            )
        return (
            f"Nota interna — {ticket.id}\n"
            f"- Asunto: {subject}\n"
            f"- Estado: {ticket.state.value if ticket.state else 'desconocido'}\n"
            f"- Próximos pasos: revisar contexto, confirmar impacto y asignar responsable.\n"
            f"- Escalar a N2 si no hay resolución en el primer toque."
        )
