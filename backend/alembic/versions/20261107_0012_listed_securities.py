"""directory of every NSE, BSE and US listed security

Revision ID: 20261107_0012
Revises: 20261103_0011
Create Date: 2026-11-07 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261107_0012'
down_revision: str | None = '20261103_0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'listed_securities',
        sa.Column('ticker', sa.String(length=20), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('exchange', sa.String(length=20), nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=True),
        sa.Column('is_etf', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_listed_securities_exchange', 'listed_securities', ['exchange'])


def downgrade() -> None:
    op.drop_index('ix_listed_securities_exchange', table_name='listed_securities')
    op.drop_table('listed_securities')
