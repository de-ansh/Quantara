"""Quarterly results from NSE integrated filings, and when each stock was last checked for them

Revision ID: 20261111_0020
Revises: 20261110_0019
Create Date: 2026-11-11 16:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261111_0020'
down_revision: str | None = '20261110_0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'quarterly_results',
        sa.Column('ticker', sa.String(length=20), primary_key=True),
        sa.Column('quarter_end', sa.Date(), primary_key=True),
        sa.Column('consolidated', sa.Boolean(), nullable=False),
        sa.Column('revenue', sa.Float(), nullable=True, comment='Revenue from operations, rupees'),
        sa.Column('profit', sa.Float(), nullable=True, comment='Profit for the period, rupees'),
        sa.Column('eps', sa.Float(), nullable=True),
        sa.Column('filed_at', sa.DateTime(), nullable=True),
        sa.Column('pdf_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.add_column('stocks', sa.Column('results_checked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('stocks', 'results_checked_at')
    op.drop_table('quarterly_results')
