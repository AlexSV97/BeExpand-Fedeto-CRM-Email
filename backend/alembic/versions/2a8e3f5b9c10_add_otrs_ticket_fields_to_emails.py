"""add_otrs_ticket_fields_to_emails

Revision ID: 2a8e3f5b9c10
Revises: f75fefbd4a00
Create Date: 2026-06-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a8e3f5b9c10'
down_revision: Union[str, Sequence[str], None] = 'f75fefbd4a00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add otrs_ticket fields to emails table."""
    op.add_column("emails", sa.Column("otrs_ticket_id", sa.String(length=100), nullable=True))
    op.add_column(
        "emails",
        sa.Column("otrs_ticket_created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema — remove otrs_ticket fields from emails table."""
    op.drop_column("emails", "otrs_ticket_created_at")
    op.drop_column("emails", "otrs_ticket_id")
