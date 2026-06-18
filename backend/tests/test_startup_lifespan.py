from __future__ import annotations

import asyncio

import pytest

from src.api import main


@pytest.mark.asyncio
async def test_lifespan_seeds_knowledge_vault_during_startup(monkeypatch):
    calls: list[str] = []

    async def fake_init_db():
        calls.append("init_db")

    async def fake_recover_orphan_tasks():
        calls.append("recover_orphan_tasks")

    async def fake_seed_admin():
        calls.append("seed_admin")

    async def fake_seed_queues():
        calls.append("seed_queues")

    async def fake_seed_knowledge_vault():
        calls.append("seed_knowledge_vault")

    async def fake_check_production_settings():
        calls.append("check_production_settings")

    async def fake_auto_sync_loop():
        calls.append("auto_sync_loop_started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("auto_sync_loop_cancelled")
            raise

    async def fake_sla_alert_loop():
        calls.append("sla_alert_loop_started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            calls.append("sla_alert_loop_cancelled")
            raise

    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main, "_recover_orphan_tasks", fake_recover_orphan_tasks)
    monkeypatch.setattr(main, "seed_admin", fake_seed_admin)
    monkeypatch.setattr(main, "seed_queues", fake_seed_queues)
    monkeypatch.setattr(main, "seed_knowledge_vault", fake_seed_knowledge_vault)
    monkeypatch.setattr(main, "_check_production_settings", fake_check_production_settings)
    monkeypatch.setattr(main, "_auto_sync_loop", fake_auto_sync_loop)
    monkeypatch.setattr(main, "_sla_alert_loop", fake_sla_alert_loop)

    async with main.lifespan(object()):
        await asyncio.sleep(0)

    assert calls[:6] == [
        "init_db",
        "recover_orphan_tasks",
        "seed_admin",
        "seed_queues",
        "seed_knowledge_vault",
        "check_production_settings",
    ]
    assert "auto_sync_loop_started" in calls
    assert "sla_alert_loop_started" in calls
    assert "auto_sync_loop_cancelled" in calls
    assert "sla_alert_loop_cancelled" in calls
