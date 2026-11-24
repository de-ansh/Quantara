"""Imported tradebook trades per portfolio, for buy dates, tax-aware rebalancing and XIRR

Revision ID: 20261124_0028
Revises: 20261124_0027
Create Date: 2026-11-24 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20261124_0028'
down_revision: str | None = '20261124_0027'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("tradebook", sa.JSON(), nullable=True))
    op.create_table(
        "portfolio_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
    )
    op.create_index("ix_portfolio_trades_portfolio_id", "portfolio_trades", ["portfolio_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_trades_portfolio_id", "portfolio_trades")
    op.drop_table("portfolio_trades")
    op.drop_column("portfolios", "tradebook")
