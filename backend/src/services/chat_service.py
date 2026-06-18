"""
ChatService — servicio de chat contextual con memoria de conversación.

Usa LLM cloud (OpenRouter) o local (Ollama) según configuración.
Antes de cada respuesta, fetchea datos actuales del sistema (stats, últimos
correos, contactos) y los inyecta en el system prompt para que el LLM pueda
responder preguntas sobre datos reales.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Email
from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres un asistente de onboarding para Aiuken SOC, desarrollado para Aiuken. Tu función es ayudar a los usuarios a entender y usar la herramienta.

CONTEXTO ACTUAL DEL SISTEMA:
{context}

INFORMACIÓN QUE DEBES CONOCER:
- La herramienta clasifica correos automáticamente usando 3 clasificadores en paralelo: RuleEngine (reglas), BERT (IA), y LLM (Hermes 3). Luego un VoteResolver combina los votos por consenso, mayoría, o juez LLM.
- Categorías: "cliente" (ya usa servicios), "lead" (potencial cliente), "proveedor" (externo), "nulo" (spam/newsletter).
- Los correos clasificados se mueven automáticamente a carpetas IMAP (Clientes, Leads, Proveedores).
- El dashboard muestra KPIs, contactos, oportunidades, y forecast a 30/60/90 días.
- Los contactos tienen categoría, empresa, cargo, email.
- Las oportunidades tienen etapa, valor, probabilidad, fecha de cierre esperada.
- Los correos urgentes tienen prioridad "alta" en el análisis.
- Los usuarios pueden revisar y corregir clasificaciones manualmente desde el detalle del email.
- El chat de onboarding NO modifica datos, solo informa y orienta.

REGLAS:
- Responde siempre en español, tono amable y profesional.
- Si te preguntan sobre datos, usa las estadísticas del contexto proporcionado.
- Si algo requiere acción (ej: revisar una clasificación), indica que deben hacerlo desde el dashboard.
- Si no sabes algo, dilo honestamente.
- Sé conciso: responde en 2-3 párrafos máximo.
- No des consejos financieros ni legales."""


# ── Servicio ──────────────────────────────────────────────────────────────────


class ChatService:
    """Servicio de chat contextual con memoria de conversación en memoria."""

    def __init__(self) -> None:
        self._conversations: dict[str, list[dict]] = {}
        self._max_history = 20
        self._client = LLMClient(use_chat_model=True)

    async def _get_system_context(self, db: AsyncSession) -> str:
        """Obtiene datos actuales del sistema para contextualizar las respuestas."""
        today = datetime.now(timezone.utc).date()

        # ── Total emails ──
        total_emails = await db.scalar(select(func.count(Email.id))) or 0

        # ── Emails today ──
        emails_today = await db.scalar(
            select(func.count(Email.id)).where(func.date(Email.received_at) == today)
        ) or 0

        # ── Contacts by category ──
        from src.db.models import Contact

        contacts_result = await db.execute(
            select(Contact.category, func.count(Contact.id))
            .group_by(Contact.category)
        )
        contacts_by_cat: dict[str, int] = {
            r.category or "sin_categoria": r[1] for r in contacts_result.all()
        }

        # ── Recent 5 emails ──
        recent_result = await db.execute(
            select(Email)
            .order_by(desc(Email.received_at))
            .limit(5)
        )
        recent_emails = recent_result.scalars().all()

        # ── Urgent count from recent emails ──
        urgent_count = 0
        urgent_senders: list[str] = []
        for email in recent_emails:
            extra = email.extra_data or {}
            analyzer = extra.get("analyzer", {})
            if analyzer.get("urgency") == "alta":
                urgent_count += 1
                urgent_senders.append(email.sender_name or email.sender_email or "")

        # ── Build context string ──
        lines = [
            f"📊 Total correos procesados: {total_emails}",
            f"📧 Correos hoy: {emails_today}",
            f"👥 Contactos por categoría: {json.dumps(contacts_by_cat, ensure_ascii=False)}",
        ]

        if urgent_count > 0:
            senders_str = ", ".join(filter(None, urgent_senders))
            lines.append(f"🔴 Correos urgentes recientes: {urgent_count} ({senders_str})")

        if recent_emails:
            lines.append("\n📨 Últimos correos:")
            for e in recent_emails:
                subject = e.subject or "(sin asunto)"
                sender = e.sender_name or e.sender_email or "(desconocido)"
                cat = e.category or "pendiente"
                lines.append(f"  - {subject} | {sender} → {cat}")

        return "\n".join(lines)

    async def get_response(
        self,
        message: str,
        conversation_id: str | None,
        db: AsyncSession,
    ) -> tuple[str, str]:
        """Procesa un mensaje y retorna (respuesta, conversation_id)."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Inicializar conversación si es nueva
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        # Obtener contexto actual del sistema
        context = await self._get_system_context(db)
        settings = get_settings()

        # Construir mensajes para el chat API
        system_msg = {"role": "system", "content": SYSTEM_PROMPT.format(context=context)}

        # Últimos exchanges para mantener contexto manejable
        history = self._conversations[conversation_id][-10:]

        messages = [system_msg] + history + [
            {"role": "user", "content": message},
        ]

        # Limpiar conversaciones viejas si hay más de 100
        if len(self._conversations) > 100:
            sorted_keys = list(self._conversations.keys())
            for k in sorted_keys[:10]:
                del self._conversations[k]

        response_text: str = ""

        try:
            response_text = await self._client.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=512,
            )

            if not response_text:
                response_text = (
                    "Lo siento, no pude generar una respuesta. "
                    "¿Puedes reformular tu pregunta?"
                )

        except Exception as e:
            response_text = (
                "Ocurrió un error al procesar tu mensaje. Inténtalo de nuevo más tarde."
            )
            logger.error("Chat error conv=%s: %s", conversation_id, e)

        # Guardar en historial
        self._conversations[conversation_id].append({"role": "user", "content": message})
        self._conversations[conversation_id].append(
            {"role": "assistant", "content": response_text}
        )

        # Podar si excede el máximo
        if len(self._conversations[conversation_id]) > self._max_history:
            self._conversations[conversation_id] = (
                self._conversations[conversation_id][-self._max_history :]
            )

        return response_text, conversation_id


# ── Singleton ─────────────────────────────────────────────────────────────────

_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Obtiene la instancia singleton del servicio de chat."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
