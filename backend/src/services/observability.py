"""ObservabilityService — RP-04.

Vista de observabilidad agregada a partir de datos reales (sin llamadas de red
externas): estado de integraciones (config + BD alcanzable), modo operativo,
actividad y fallos de ``OperationalRecord``, e intervalos de los jobs de fondo.

Latencia/coste reales quedan fuera (requieren middleware de métricas); esto es la
fase 1: salud + actividad + fallos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import OperationalRecord
from src.integrations.otrs_znuny import OtrsZnunySettings

_FAILURE_STATUSES = {"failure", "error", "failed"}


class IntegrationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    detail: str | None = None


class ObservabilitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generatedAt: str
    operatingMode: str  # live | demo
    integrations: list[IntegrationStatus]
    recordCounts: dict[str, int]
    failures: int
    autoSyncIntervalSeconds: int
    slaAlertScanIntervalSeconds: int


class ObservabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def snapshot(self) -> ObservabilitySnapshot:
        settings = get_settings()
        otrs = OtrsZnunySettings()

        # ── Actividad y fallos (OperationalRecord) ──
        db_ok = True
        record_counts: dict[str, int] = {}
        failures = 0
        try:
            rows = (
                await self.db.execute(
                    select(OperationalRecord.record_kind, func.count())
                    .group_by(OperationalRecord.record_kind)
                )
            ).all()
            record_counts = {kind: int(count) for kind, count in rows}

            fail_rows = (
                await self.db.execute(
                    select(func.count()).where(
                        func.lower(OperationalRecord.status).in_(_FAILURE_STATUSES)
                    )
                )
            ).scalar()
            failures = int(fail_rows or 0)
        except Exception:  # noqa: BLE001 — la BD es la propia señal de salud
            db_ok = False

        # ── Integraciones (config + BD) ──
        ai_status = "openrouter" if settings.openrouter_api_key else "ollama-local"
        integrations = [
            IntegrationStatus(name="database", status="ok" if db_ok else "error"),
            IntegrationStatus(
                name="otrs",
                status="configured" if otrs.is_configured else "not_configured",
                detail=(otrs.normalized_base_url or None) if otrs.is_configured else None,
            ),
            IntegrationStatus(name="ai", status=ai_status),
        ]

        return ObservabilitySnapshot(
            generatedAt=datetime.now(timezone.utc).isoformat(),
            operatingMode="live" if otrs.is_configured else "demo",
            integrations=integrations,
            recordCounts=record_counts,
            failures=failures,
            autoSyncIntervalSeconds=settings.sync_interval_seconds,
            slaAlertScanIntervalSeconds=settings.sla_alert_scan_interval_seconds,
        )
