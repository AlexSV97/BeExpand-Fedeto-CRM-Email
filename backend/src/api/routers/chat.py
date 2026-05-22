"""
Chat router — endpoint de chat contextual para el dashboard.

Usa el ChatService que corre sobre el mismo Ollama (hermes3:8b) con contexto
del sistema inyectado en cada llamada.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.models import User
from src.db.session import get_db
from src.services.chat_service import get_chat_service

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat contextual con el asistente de onboarding.

    Recibe un mensaje del usuario y opcionalmente un conversation_id para
    mantener el hilo de la conversación. Retorna la respuesta y el ID de
    conversación para usarlo en siguientes mensajes.

    El asistente tiene contexto del sistema (stats, correos recientes, etc.)
    y puede responder preguntas sobre el uso de la herramienta y datos actuales.
    """
    service = get_chat_service()
    response_text, conv_id = await service.get_response(
        body.message, body.conversation_id, db
    )
    return ChatResponse(response=response_text, conversation_id=conv_id)
