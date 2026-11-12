"""NSE bulk and block deals, one row per trade

Revision ID: 20261112_0021
Revises: 20261111_0020
Create Date: 2026-11-12 06:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261112_0021'
down_revision: str | None = '20261111_0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'large_deals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('deal_date', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(length=5), nullable=False, comment='bulk or block'),
        sa.Column('symbol', sa.String(length=20), nullable=False, comment='NSE symbol'),
        sa.Column('company', sa.String(length=200), nullable=True),
        sa.Column('client', sa.String(length=200), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False, comment='BUY or SELL'),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.UniqueConstraint('deal_date', 'kind', 'symbol', 'client', 'side', 'quantity', 'price', name='uq_large_deal'),
    )
    op.create_index(op.f('ix_large_deals_deal_date'), 'large_deals', ['deal_date'])
    op.create_index(op.f('ix_large_deals_symbol'), 'large_deals', ['symbol'])


def downgrade() -> None:
    op.drop_index(op.f('ix_large_deals_symbol'), table_name='large_deals')
    op.drop_index(op.f('ix_large_deals_deal_date'), table_name='large_deals')
    op.drop_table('large_deals')
