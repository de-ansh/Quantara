"""user-linked earnings filing per stock

Revision ID: 20261029_0010
Revises: 20261027_0009
Create Date: 2026-10-29 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261029_0010'
down_revision: str | None = '20261027_0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('stocks', sa.Column('filing_url', sa.String(length=1000), nullable=True))
    op.add_column('stocks', sa.Column('filing_text', sa.Text(), nullable=True))
    op.add_column('stocks', sa.Column('filing_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('stocks', 'filing_updated_at')
    op.drop_column('stocks', 'filing_text')
    op.drop_column('stocks', 'filing_url')
