"""create queues table with hierarchy + seed topology (CE-01)

Revision ID: b1d4c0a7e2f1
Revises: 2a8e3f5b9c10
Create Date: 2026-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1d4c0a7e2f1'
down_revision: Union[str, Sequence[str], None] = '2a8e3f5b9c10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create queues table and seed the 11-row topology."""
    queues = op.create_table(
        'queues',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tier', sa.String(length=20), nullable=True),
        sa.Column('owner', sa.String(length=100), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('otrs_external_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['queues.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_queues_name'),
        sa.UniqueConstraint('slug', name='uq_queues_slug'),
    )

    # Seed con ids explícitos para poder enlazar parent_id en el mismo insert.
    op.bulk_insert(
        queues,
        [
            {'id': 1, 'name': 'N1 - Triage', 'slug': 'n1-triage', 'tier': 'n1', 'owner': 'N1 Triage', 'parent_id': None, 'is_active': True},
            {'id': 2, 'name': 'N2 - Resolución', 'slug': 'n2-resolucion', 'tier': 'n2', 'owner': 'N2 Resolver', 'parent_id': None, 'is_active': True},
            {'id': 3, 'name': 'N3 - Ingeniería', 'slug': 'n3-ingenieria', 'tier': 'n3', 'owner': 'N3 Engineering', 'parent_id': None, 'is_active': True},
            {'id': 4, 'name': 'Special - Fabricante', 'slug': 'special-fabricante', 'tier': 'special', 'owner': 'Vendor Coordinator', 'parent_id': 3, 'is_active': True},
            {'id': 5, 'name': 'Special - External ITSM', 'slug': 'special-external-itsm', 'tier': 'special', 'owner': 'ITSM Integrations', 'parent_id': 3, 'is_active': True},
            {'id': 6, 'name': 'Special - Seguridad', 'slug': 'special-seguridad', 'tier': 'special', 'owner': 'Security Desk', 'parent_id': 2, 'is_active': True},
            {'id': 7, 'name': 'Support', 'slug': 'support', 'tier': None, 'owner': None, 'parent_id': None, 'is_active': True},
            {'id': 8, 'name': 'Ventas', 'slug': 'ventas', 'tier': None, 'owner': None, 'parent_id': None, 'is_active': True},
            {'id': 9, 'name': 'Proveedores', 'slug': 'proveedores', 'tier': None, 'owner': None, 'parent_id': None, 'is_active': True},
            {'id': 10, 'name': 'Contabilidad', 'slug': 'contabilidad', 'tier': None, 'owner': None, 'parent_id': None, 'is_active': True},
            {'id': 11, 'name': 'Direccion', 'slug': 'direccion', 'tier': None, 'owner': None, 'parent_id': None, 'is_active': True},
        ],
    )


def downgrade() -> None:
    """Downgrade schema: drop queues table."""
    op.drop_table('queues')
