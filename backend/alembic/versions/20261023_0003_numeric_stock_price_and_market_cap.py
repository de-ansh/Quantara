"""store stocks.price and stocks.market_cap as numbers instead of display strings

Revision ID: 20261023_0003
Revises: 20261021_0002
Create Date: 2026-10-23 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261023_0003"
down_revision: str | None = "20261021_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Strings like "$189.42", "₹1,215.40", "2.94T", "$558.2B" or "N/A" (-> NULL)
_DIGITS = "NULLIF(regexp_replace({col}, '[^0-9.]', '', 'g'), '')::double precision"


def upgrade() -> None:
    op.alter_column(
        "stocks",
        "price",
        type_=sa.Float(),
        existing_nullable=True,
        comment="Last price in listing currency",
        postgresql_using=_DIGITS.format(col="price"),
    )
    op.alter_column(
        "stocks",
        "market_cap",
        type_=sa.Float(),
        existing_nullable=True,
        comment="Market cap in listing currency",
        postgresql_using=(
            _DIGITS.format(col="market_cap")
            + " * CASE upper(right(trim(market_cap), 1))"
            " WHEN 'T' THEN 1e12 WHEN 'B' THEN 1e9 WHEN 'M' THEN 1e6 WHEN 'K' THEN 1e3"
            " ELSE 1 END"
        ),
    )


def downgrade() -> None:
    op.alter_column(
        "stocks",
        "market_cap",
        type_=sa.String(50),
        existing_nullable=True,
        comment="Market cap formatted",
        postgresql_using="market_cap::text",
    )
    op.alter_column(
        "stocks",
        "price",
        type_=sa.String(50),
        existing_nullable=True,
        comment="Current price formatted",
        postgresql_using="price::text",
    )
