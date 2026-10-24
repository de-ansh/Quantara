"""price alerts

Revision ID: 20261023_0008
Revises: 20261023_0007
Create Date: 2026-10-23 18:28:13.335007

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261023_0008'
down_revision: str | None = '20261023_0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('price_alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('direction', sa.String(length=5), nullable=False, comment='above | below'),
    sa.Column('target_price', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('triggered_at', sa.DateTime(), nullable=True),
    sa.Column('triggered_price', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_alerts_id'), 'price_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_price_alerts_triggered_at'), 'price_alerts', ['triggered_at'], unique=False)
    op.create_index(op.f('ix_price_alerts_user_id'), 'price_alerts', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_price_alerts_user_id'), table_name='price_alerts')
    op.drop_index(op.f('ix_price_alerts_triggered_at'), table_name='price_alerts')
    op.drop_index(op.f('ix_price_alerts_id'), table_name='price_alerts')
    op.drop_table('price_alerts')
