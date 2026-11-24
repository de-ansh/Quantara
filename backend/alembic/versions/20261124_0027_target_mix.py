"""Users' target asset mix for rebalancing

Revision ID: 20261124_0027
Revises: 20261123_0026
Create Date: 2026-11-24 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20261124_0027'
down_revision: str | None = '20261123_0026'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("target_mix", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "target_mix")
