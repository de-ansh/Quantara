"""stock fundamentals_updated_at and drop delisted TATAMOTORS.NS

Revision ID: 20261023_0007
Revises: 20261023_0006
Create Date: 2026-10-23 16:37:38.288854

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261023_0007'
down_revision: str | None = '20261023_0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Every table with a foreign key to stocks.ticker
_REFERENCING = [
    "signals", "portfolio_positions", "watchlist_items",
    "recommendations", "research_reports", "document_chunks",
]


def upgrade() -> None:
    op.add_column('stocks', sa.Column('fundamentals_updated_at', sa.DateTime(), nullable=True, comment='When market cap / P/E / beta were last fetched'))


    # TATAMOTORS.NS stopped trading after the Tata Motors demerger (seed now uses TMCV.NS).
    # Remove it only when nothing references it, so no user data is touched.
    unreferenced = " AND ".join(
        f"NOT EXISTS (SELECT 1 FROM {t} WHERE {t}.ticker = stocks.ticker)" for t in _REFERENCING
    )
    op.execute(f"DELETE FROM stocks WHERE ticker = 'TATAMOTORS.NS' AND {unreferenced}")


def downgrade() -> None:
    # The deleted delisted row is not restored; it had no live data.
    op.drop_column('stocks', 'fundamentals_updated_at')
