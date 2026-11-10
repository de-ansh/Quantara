"""end-of-day prices on directory rows (Indian listings, from BSE's bhavcopy)

Revision ID: 20261109_0016
Revises: 20261109_0015
Create Date: 2026-11-09 15:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261109_0016'
down_revision: str | None = '20261109_0015'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('listed_securities', sa.Column('close', sa.Float(), nullable=True))
    op.add_column('listed_securities', sa.Column('prev_close', sa.Float(), nullable=True))
    op.add_column('listed_securities', sa.Column('price_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('listed_securities', 'price_date')
    op.drop_column('listed_securities', 'prev_close')
    op.drop_column('listed_securities', 'close')
