"""watchlist items and user token_version

Revision ID: 20261023_0004
Revises: 20261023_0003
Create Date: 2026-10-23 14:30:07.454892

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261023_0004'
down_revision: str | None = '20261023_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('watchlist_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'ticker', name='uq_watchlist_user_ticker')
    )
    op.create_index(op.f('ix_watchlist_items_id'), 'watchlist_items', ['id'], unique=False)
    op.create_index(op.f('ix_watchlist_items_user_id'), 'watchlist_items', ['user_id'], unique=False)
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
    op.drop_index(op.f('ix_watchlist_items_user_id'), table_name='watchlist_items')
    op.drop_index(op.f('ix_watchlist_items_id'), table_name='watchlist_items')
    op.drop_table('watchlist_items')
