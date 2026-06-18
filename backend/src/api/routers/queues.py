"""Queue topology and escalation recommendation router."""

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.db.models import User
from src.services.queue_strategy import (
    QueueDecision,
    QueueDecisionRequest,
    QueueStrategyService,
    QueueTopology,
    get_queue_strategy_service,
)
from src.services.queue_suggestion import (
    QueueSuggestion,
    QueueSuggestionRequest,
    QueueSuggestionService,
)

router = APIRouter(tags=["queues"])


@router.get("/queues/topology", response_model=QueueTopology)
async def get_queue_topology(
    current_user: User = Depends(get_current_user),
    service: QueueStrategyService = Depends(get_queue_strategy_service),
):
    return service.topology()


@router.post("/queues/recommendation", response_model=QueueDecision)
async def recommend_queue_decision(
    body: QueueDecisionRequest,
    current_user: User = Depends(get_current_user),
    service: QueueStrategyService = Depends(get_queue_strategy_service),
):
    return service.recommend(body)


@router.post("/queues/suggestion", response_model=QueueSuggestion)
async def suggest_queue(
    body: QueueSuggestionRequest,
    current_user: User = Depends(get_current_user),
    service: QueueStrategyService = Depends(get_queue_strategy_service),
):
    """Sugerencia de cola asistida por IA (CE-02) con fallback a reglas."""
    suggester = QueueSuggestionService(strategy=service)
    return await suggester.suggest(body)
