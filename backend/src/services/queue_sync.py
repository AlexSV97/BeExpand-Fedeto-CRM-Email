"""QueueSyncService — CE-01.

Sincroniza el árbol de colas desde OTRS hacia la tabla local ``queues`` y, si
OTRS no está disponible, garantiza la topología conocida vía seed. Es la fuente
de verdad única que consumen ``QueueStrategyService`` y ``ActionExecutor``.

Contratos (REQ-2, REQ-3, REQ-5, NFR-2):
    - ``sync_from_otrs()``  → upsert idempotente desde ``list_queues()``.
    - ``ensure_seeded()``   → inserta los 6 nodos de topología si la tabla está vacía.
    - ``get_topology()``    → construye un ``QueueTopology`` desde la BD.
    - ``get_by_name()``     → busca una cola activa por nombre.
"""

from __future__ import annotations

import logging
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import QueueModel
from src.domain.ticketing import Queue
from src.services.queue_strategy import QueueTier, QueueTopology, QueueTopologyNode

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    folded = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return "-".join(part for part in folded.replace("/", " ").split() if part)


# ── Seed de topología (REQ-5): 6 nodos N1/N2/N3 + 3 especiales ──────────────
# parent referencia el slug del padre (None = raíz).
_TIER_SEED: list[dict] = [
    {"name": "N1 - Triage", "slug": "n1-triage", "tier": "n1", "owner": "N1 Triage", "parent": None},
    {"name": "N2 - Resolución", "slug": "n2-resolucion", "tier": "n2", "owner": "N2 Resolver", "parent": None},
    {"name": "N3 - Ingeniería", "slug": "n3-ingenieria", "tier": "n3", "owner": "N3 Engineering", "parent": None},
    {"name": "Special - Fabricante", "slug": "special-fabricante", "tier": "special", "owner": "Vendor Coordinator", "parent": "n3-ingenieria"},
    {"name": "Special - External ITSM", "slug": "special-external-itsm", "tier": "special", "owner": "ITSM Integrations", "parent": "n3-ingenieria"},
    {"name": "Special - Seguridad", "slug": "special-seguridad", "tier": "special", "owner": "Security Desk", "parent": "n2-resolucion"},
]

# Colas de negocio (sin tier): destino de routing por categoría/departamento.
# La migración Alembic las siembra junto a la topología; aquí están para que
# sync/seed produzcan un árbol completo cuando se ejecuta en runtime.
_BUSINESS_SEED: list[dict] = [
    {"name": "Support", "slug": "support", "tier": None, "owner": None, "parent": None},
    {"name": "Ventas", "slug": "ventas", "tier": None, "owner": None, "parent": None},
    {"name": "Proveedores", "slug": "proveedores", "tier": None, "owner": None, "parent": None},
    {"name": "Contabilidad", "slug": "contabilidad", "tier": None, "owner": None, "parent": None},
    {"name": "Direccion", "slug": "direccion", "tier": None, "owner": None, "parent": None},
]

# Mapa slug → slug del padre, para inferir jerarquía al sincronizar desde OTRS
# (que no suele exponer parent_id).
_PARENT_BY_SLUG: dict[str, str] = {
    row["slug"]: row["parent"] for row in _TIER_SEED if row["parent"]
}


class QueueSyncService:
    def __init__(self, db: AsyncSession, otrs_client=None) -> None:
        self.db = db
        self._otrs_client = otrs_client

    # ── Sync ────────────────────────────────────────────────────────────
    async def sync_from_otrs(self) -> int:
        """Upsert de colas desde OTRS. Fail-open: si OTRS no responde, seed.

        Returns: número de colas upserted (0 si se usó el fallback de seed).
        """
        try:
            client = self._otrs_client
            if client is None:
                from src.integrations.otrs_znuny.client import OtrsZnunyClient

                client = OtrsZnunyClient()
            otrs_queues = await client.list_queues()
        except Exception as exc:  # noqa: BLE001 — fail-open por diseño
            logger.warning("OTRS no disponible para sync de colas (%s); usando seed", exc)
            await self.ensure_seeded()
            return 0

        count = 0
        for queue in otrs_queues:
            await self._upsert(queue)
            count += 1
        await self.db.flush()

        # Resolver parent_id por convención de slug tras el upsert
        await self._resolve_parents()
        await self.db.commit()

        if count == 0:
            await self.ensure_seeded()
        return count

    async def _upsert(self, queue: Queue) -> QueueModel:
        slug = queue.slug or _slugify(queue.name)
        existing = await self._get_model_by_name(queue.name)
        external_id = queue.id or (
            queue.external_refs[0].external_id if queue.external_refs else None
        )
        if existing is not None:
            existing.slug = slug
            if external_id:
                existing.otrs_external_id = external_id
            if queue.owner:
                existing.owner = queue.owner
            if queue.tier:
                existing.tier = queue.tier
            existing.is_active = queue.is_active
            return existing

        model = QueueModel(
            name=queue.name,
            slug=slug,
            tier=queue.tier,
            owner=queue.owner,
            otrs_external_id=external_id,
            is_active=queue.is_active,
        )
        self.db.add(model)
        return model

    async def _resolve_parents(self) -> None:
        """Asigna parent_id según la convención de slugs conocida."""
        rows = (await self.db.execute(select(QueueModel))).scalars().all()
        by_slug = {row.slug: row for row in rows}
        for row in rows:
            parent_slug = _PARENT_BY_SLUG.get(row.slug)
            if parent_slug and parent_slug in by_slug and row.parent_id is None:
                row.parent_id = by_slug[parent_slug].id

    # ── Seed ────────────────────────────────────────────────────────────
    async def ensure_seeded(self) -> None:
        """Inserta la topología de 6 nodos si la tabla ``queues`` está vacía."""
        existing = (await self.db.execute(select(QueueModel.id).limit(1))).first()
        if existing is not None:
            return

        slug_to_model: dict[str, QueueModel] = {}
        # Primera pasada: insertar nodos sin parent.
        for row in _TIER_SEED:
            model = QueueModel(
                name=row["name"],
                slug=row["slug"],
                tier=row["tier"],
                owner=row["owner"],
                is_active=True,
            )
            self.db.add(model)
            slug_to_model[row["slug"]] = model
        await self.db.flush()

        # Segunda pasada: enlazar parent_id por slug.
        for row in _TIER_SEED:
            if row["parent"]:
                slug_to_model[row["slug"]].parent_id = slug_to_model[row["parent"]].id

        await self.db.commit()

    async def seed_defaults(self) -> None:
        """Garantiza las 11 colas por defecto (6 topología + 5 de negocio).

        Idempotente por nombre: solo inserta las que falten. Pensado para el
        arranque de la app (lifespan), donde ``create_all`` crea la tabla pero
        las migraciones de seed no se ejecutan. A diferencia de
        ``ensure_seeded`` (6 filas, fallback de sync), aquí también se siembran
        las colas de negocio necesarias para la validación de ``ActionExecutor``.
        """
        existing_names = set(
            (await self.db.execute(select(QueueModel.name))).scalars().all()
        )
        created = False
        for row in (*_TIER_SEED, *_BUSINESS_SEED):
            if row["name"] not in existing_names:
                self.db.add(
                    QueueModel(
                        name=row["name"],
                        slug=row["slug"],
                        tier=row["tier"],
                        owner=row["owner"],
                        is_active=True,
                    )
                )
                created = True

        if not created:
            return

        await self.db.flush()
        await self._resolve_parents()
        await self.db.commit()

    # ── Lectura ─────────────────────────────────────────────────────────
    async def get_by_name(self, name: str) -> QueueModel | None:
        return await self._get_model_by_name(name, active_only=True)

    async def _get_model_by_name(self, name: str, active_only: bool = False) -> QueueModel | None:
        stmt = select(QueueModel).where(QueueModel.name == name)
        if active_only:
            stmt = stmt.where(QueueModel.is_active.is_(True))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_topology(self) -> QueueTopology:
        """Construye un ``QueueTopology`` desde las filas de la BD.

        roots = colas con tier n1/n2/n3; special_queues = colas con tier special.
        Las colas de negocio (tier None) no forman parte de la topología.
        """
        rows = (
            await self.db.execute(
                select(QueueModel).where(QueueModel.is_active.is_(True))
            )
        ).scalars().all()

        by_id = {row.id: row for row in rows}

        roots: list[QueueTopologyNode] = []
        specials: list[QueueTopologyNode] = []
        for row in rows:
            if row.tier is None:
                continue
            tier = QueueTier(row.tier)
            node = self._to_node(row, tier, by_id)
            if tier == QueueTier.SPECIAL:
                specials.append(node)
            else:
                roots.append(node)

        roots.sort(key=lambda n: n.tier.value)
        specials.sort(key=lambda n: n.name)
        return QueueTopology(roots=roots, special_queues=specials)

    @staticmethod
    def _to_node(row: QueueModel, tier: QueueTier, by_id: dict[int, QueueModel]) -> QueueTopologyNode:
        parent_slug = by_id[row.parent_id].slug if row.parent_id in by_id else None
        return QueueTopologyNode(
            name=row.name,
            tier=tier,
            owner=row.owner or row.name,
            queue=Queue(
                id=str(row.id),
                name=row.name,
                slug=row.slug,
                parent_id=parent_slug,
                tier=row.tier,
                owner=row.owner,
                is_active=row.is_active,
                metadata=row.queue_metadata or {"tier": row.tier},
            ),
        )
