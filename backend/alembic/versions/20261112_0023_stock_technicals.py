"""Daily technical snapshot per stock, for screener filters and the most-traded list

Revision ID: 20261112_0023
Revises: 20261112_0022
Create Date: 2026-11-12 10:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261112_0023'
down_revision: str | None = '20261112_0022'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ('rsi_14', sa.Float(), None),
    ('sma50_gap_pct', sa.Float(), 'Price vs 50-day average, %'),
    ('sma200_gap_pct', sa.Float(), 'Price vs 200-day average, %'),
    ('from_high_52w_pct', sa.Float(), 'Price vs 52-week high, % (<= 0)'),
    ('from_low_52w_pct', sa.Float(), 'Price vs 52-week low, % (>= 0)'),
    ('turnover_1d', sa.Float(), "Last session's traded value, listing currency"),
    ('turnover_20d', sa.Float(), '20-session average traded value'),
    ('technicals_updated_at', sa.DateTime(), None),
]


def upgrade() -> None:
    for name, type_, comment in COLUMNS:
        op.add_column('stocks', sa.Column(name, type_, nullable=True, comment=comment))


def downgrade() -> None:
    for name, _, _ in reversed(COLUMNS):
        op.drop_column('stocks', name)
