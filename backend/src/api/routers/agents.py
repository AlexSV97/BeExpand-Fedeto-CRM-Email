from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.models import OperationalRecord, User
from src.db.session import get_db
from src.services.agent_governance import (
    AgentApprovalRequest,
    AgentAuditTrail,
    AgentGovernanceService,
    AgentRecommendationRequest,
    AgentRecommendationResponse,
    AgentApprovalRecord,
)

router = APIRouter(tags=["agents"])


def get_agent_governance_service(request: Request) -> AgentGovernanceService:
    service = getattr(request.app.state, "agent_governance_service", None)
    if isinstance(service, AgentGovernanceService):
        return service
    service = AgentGovernanceService()
    request.app.state.agent_governance_service = service
    return service


def _serialize_record(record: OperationalRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "record_kind": record.record_kind,
        "resource_id": record.resource_id,
        "actor_kind": record.actor_kind,
        "actor_name": record.actor_name,
        "status": record.status,
        "title": record.title,
        "payload": record.payload,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.post("/agents/recommendation", response_model=AgentRecommendationResponse)
async def recommend_agent_plan(
    body: AgentRecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    response = service.recommend(body)
    await service.persist_recommendation(db, response.recommendation_id, body, response)
    if service.audit_log():
        await service.persist_audit_event(db, service.audit_log()[-1])
    return response


@router.post("/agents/approvals", response_model=AgentApprovalRecord)
async def approve_agent_plan(
    body: AgentApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    record = service.approve(body)
    await service.persist_approval(db, body, record)
    if service.audit_log():
        await service.persist_audit_event(db, service.audit_log()[-1])
    return record


@router.get("/agents/audit", response_model=AgentAuditTrail)
async def list_agent_audit(
    current_user: User = Depends(get_current_user),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    return AgentAuditTrail(items=service.audit_log())


@router.get("/agents/history")
async def list_agent_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    records = await service.list_history(db, limit=limit)
    return {"items": [_serialize_record(record) for record in records], "total": len(records)}
