"""fundamentals for screening: ROE, debt/equity, growth, margin, dividend yield, 1-year return

Revision ID: 20261110_0017
Revises: 20261109_0016
Create Date: 2026-11-10 10:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261110_0017'
down_revision: str | None = '20261109_0016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("roe_pct", "debt_to_equity", "revenue_growth_pct", "profit_margin_pct", "dividend_yield_pct", "return_1y_pct")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column('stocks', sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column('stocks', name)
