from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_current_user
from src.db.models import User
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


@router.post("/agents/recommendation", response_model=AgentRecommendationResponse)
async def recommend_agent_plan(
    body: AgentRecommendationRequest,
    current_user: User = Depends(get_current_user),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    return service.recommend(body)


@router.post("/agents/approvals", response_model=AgentApprovalRecord)
async def approve_agent_plan(
    body: AgentApprovalRequest,
    current_user: User = Depends(get_current_user),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    return service.approve(body)


@router.get("/agents/audit", response_model=AgentAuditTrail)
async def list_agent_audit(
    current_user: User = Depends(get_current_user),
    service: AgentGovernanceService = Depends(get_agent_governance_service),
):
    return AgentAuditTrail(items=service.audit_log())
