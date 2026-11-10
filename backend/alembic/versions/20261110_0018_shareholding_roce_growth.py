"""ROCE, 3-year growth and promoter holding on stocks; quarterly promoter holding history

Revision ID: 20261110_0018
Revises: 20261110_0017
Create Date: 2026-11-10 14:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261110_0018'
down_revision: str | None = '20261110_0017'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FLOATS = ("roce_pct", "revenue_cagr_3y_pct", "profit_cagr_3y_pct", "promoter_pct", "promoter_change_pp")


def upgrade() -> None:
    for name in FLOATS:
        op.add_column('stocks', sa.Column(name, sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('statements_updated_at', sa.DateTime(), nullable=True))
    op.add_column('stocks', sa.Column('shareholding_quarter', sa.Date(), nullable=True))
    op.create_table(
        'shareholdings',
        sa.Column('ticker', sa.String(length=20), primary_key=True),
        sa.Column('quarter', sa.Date(), primary_key=True),
        sa.Column('promoter_pct', sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('shareholdings')
    op.drop_column('stocks', 'shareholding_quarter')
    op.drop_column('stocks', 'statements_updated_at')
    for name in reversed(FLOATS):
        op.drop_column('stocks', name)
