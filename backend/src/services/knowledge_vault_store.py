from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Setting
from src.services.knowledge_vault import KnowledgeVaultService

KNOWLEDGE_VAULT_SNAPSHOT_KEY = "knowledge_vault_snapshot"


async def load_knowledge_vault_snapshot(session: AsyncSession) -> dict[str, Any] | None:
    result = await session.execute(select(Setting).where(Setting.key == KNOWLEDGE_VAULT_SNAPSHOT_KEY))
    setting = result.scalar_one_or_none()
    if setting is None or not setting.value.strip():
        return None
    try:
        return json.loads(setting.value)
    except json.JSONDecodeError:
        return None


async def save_knowledge_vault_snapshot(session: AsyncSession, vault: KnowledgeVaultService) -> None:
    payload = json.dumps(vault.to_snapshot(), ensure_ascii=False)
    result = await session.execute(select(Setting).where(Setting.key == KNOWLEDGE_VAULT_SNAPSHOT_KEY))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = Setting(key=KNOWLEDGE_VAULT_SNAPSHOT_KEY, value=payload)
        session.add(setting)
    else:
        setting.value = payload
    await session.commit()
