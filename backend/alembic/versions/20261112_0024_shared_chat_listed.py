"""Opt-in gallery listing for shared chats

Revision ID: 20261112_0024
Revises: 20261112_0023
Create Date: 2026-11-12 14:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261112_0024'
down_revision: str | None = '20261112_0023'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('shared_chats', sa.Column('listed', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('shared_chats', 'listed')
