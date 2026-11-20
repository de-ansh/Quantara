"""Mutual fund schemes (AMFI NAVs) and fund holdings in portfolios

Revision ID: 20261120_0025
Revises: 20261112_0024
Create Date: 2026-11-20 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261120_0025'
down_revision: str | None = '20261112_0024'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'mutual_funds',
        sa.Column('scheme_code', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=150), nullable=True),
        sa.Column('isin', sa.String(length=12), nullable=True),
        sa.Column('isin_reinvest', sa.String(length=12), nullable=True),
        sa.Column('nav', sa.Float(), nullable=False),
        sa.Column('prev_nav', sa.Float(), nullable=True),
        sa.Column('nav_date', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('scheme_code'),
    )
    op.create_index(op.f('ix_mutual_funds_isin'), 'mutual_funds', ['isin'], unique=False)
    op.create_index(op.f('ix_mutual_funds_isin_reinvest'), 'mutual_funds', ['isin_reinvest'], unique=False)
    op.create_table(
        'portfolio_funds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('scheme_code', sa.Integer(), nullable=False),
        sa.Column('units', sa.Float(), nullable=False),
        sa.Column('cost_basis', sa.Float(), nullable=False, comment='Average cost per unit'),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scheme_code'], ['mutual_funds.scheme_code']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portfolio_funds_portfolio_id'), 'portfolio_funds', ['portfolio_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_funds_portfolio_id'), table_name='portfolio_funds')
    op.drop_table('portfolio_funds')
    op.drop_index(op.f('ix_mutual_funds_isin_reinvest'), table_name='mutual_funds')
    op.drop_index(op.f('ix_mutual_funds_isin'), table_name='mutual_funds')
    op.drop_table('mutual_funds')
