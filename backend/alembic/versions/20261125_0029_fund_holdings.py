"""What each mutual fund owns: its latest monthly portfolio, for look-through exposure

Revision ID: 20261125_0029
Revises: 20261124_0028
Create Date: 2026-11-25 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20261125_0029'
down_revision: str | None = '20261124_0028'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mutual_funds", sa.Column("groww_id", sa.String(150), nullable=True))
    op.add_column("mutual_funds", sa.Column("holdings_as_of", sa.Date(), nullable=True))
    op.add_column("mutual_funds", sa.Column("holdings_checked_at", sa.DateTime(), nullable=True))
    op.create_table(
        "fund_holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_code", sa.Integer(),
                  sa.ForeignKey("mutual_funds.scheme_code", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
    )
    op.create_index("ix_fund_holdings_scheme_code", "fund_holdings", ["scheme_code"])


def downgrade() -> None:
    op.drop_index("ix_fund_holdings_scheme_code", "fund_holdings")
    op.drop_table("fund_holdings")
    op.drop_column("mutual_funds", "holdings_checked_at")
    op.drop_column("mutual_funds", "holdings_as_of")
    op.drop_column("mutual_funds", "groww_id")
