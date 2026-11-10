"""daily verdict snapshots, to measure how verdicts turn out

Revision ID: 20261109_0015
Revises: 20261108_0014
Create Date: 2026-11-09 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261109_0015'
down_revision: str | None = '20261108_0014'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'verdict_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('verdict', sa.String(length=10), nullable=False),
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('day', 'ticker', 'risk_level', name='uq_verdict_snapshot_day'),
    )
    op.create_index('ix_verdict_snapshots_day', 'verdict_snapshots', ['day'])
    op.create_index('ix_verdict_snapshots_ticker', 'verdict_snapshots', ['ticker'])


def downgrade() -> None:
    op.drop_index('ix_verdict_snapshots_ticker', table_name='verdict_snapshots')
    op.drop_index('ix_verdict_snapshots_day', table_name='verdict_snapshots')
    op.drop_table('verdict_snapshots')
