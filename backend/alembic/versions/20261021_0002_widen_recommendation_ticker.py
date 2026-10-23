"""widen recommendations.ticker to 20 chars for NSE/BSE tickers (e.g. HDFCBANK.NS)

Revision ID: 20261021_0002
Revises: 20261020_0001
Create Date: 2026-10-21 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261021_0002"
down_revision: str | None = "20261020_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("recommendations", "ticker", type_=sa.String(20), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("recommendations", "ticker", type_=sa.String(10), existing_nullable=False)
