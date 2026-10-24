"""stock previous_close and price_updated_at

Revision ID: 20261023_0006
Revises: 20261023_0005
Create Date: 2026-10-23 15:58:07.915701

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261023_0006'
down_revision: str | None = '20261023_0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('stocks', sa.Column('previous_close', sa.Float(), nullable=True, comment='Prior session close, for day change'))
    op.add_column('stocks', sa.Column('price_updated_at', sa.DateTime(), nullable=True, comment='When price was last fetched from the market'))


def downgrade() -> None:
    op.drop_column('stocks', 'price_updated_at')
    op.drop_column('stocks', 'previous_close')
