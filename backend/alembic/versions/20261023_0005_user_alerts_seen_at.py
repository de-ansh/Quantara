"""user alerts_seen_at

Revision ID: 20261023_0005
Revises: 20261023_0004
Create Date: 2026-10-23 15:11:09.885665

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261023_0005'
down_revision: str | None = '20261023_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('alerts_seen_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'alerts_seen_at')
