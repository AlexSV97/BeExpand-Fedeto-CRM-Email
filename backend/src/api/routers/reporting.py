from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.models import OperationalRecord, User
from src.db.session import get_db
from src.services.reporting import (
    AnalystFeedbackRequest,
    FeedbackLoopResponse,
    FeedbackLoopService,
    OperationalReport,
    OperationalReportPayload,
    OperationalReportRequest,
    ReportWindow,
    ReportingService,
)

router = APIRouter(tags=["reporting"])


def get_reporting_service(request: Request) -> ReportingService:
    service = getattr(request.app.state, "reporting_service", None)
    if isinstance(service, ReportingService):
        return service
    service = ReportingService()
    request.app.state.reporting_service = service
    return service


def get_feedback_loop_service(request: Request) -> FeedbackLoopService:
    service = getattr(request.app.state, "feedback_loop_service", None)
    if isinstance(service, FeedbackLoopService):
        return service
    service = FeedbackLoopService()
    request.app.state.feedback_loop_service = service
    return service


@router.post("/reporting/daily", response_model=OperationalReport)
async def daily_report(
    body: OperationalReportPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: ReportingService = Depends(get_reporting_service),
):
    request = OperationalReportRequest(window=ReportWindow.DAILY, **body.model_dump())
    report = service.generate_report(request)
    await service.persist_report(db, report)
    return report


@router.post("/reporting/weekly", response_model=OperationalReport)
async def weekly_report(
    body: OperationalReportPayload,
    current_user: User = Depends(get_current_user),
    service: ReportingService = Depends(get_reporting_service),
):
    request = OperationalReportRequest(window=ReportWindow.WEEKLY, **body.model_dump())
    return service.generate_report(request)


@router.post("/reporting/feedback", response_model=FeedbackLoopResponse)
async def record_feedback(
    body: AnalystFeedbackRequest,
    current_user: User = Depends(get_current_user),
    service: FeedbackLoopService = Depends(get_feedback_loop_service),
):
    return service.record_feedback(body)
