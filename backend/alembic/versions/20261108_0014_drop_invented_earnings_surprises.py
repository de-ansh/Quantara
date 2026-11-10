"""delete earnings-surprise signals built from an invented estimate

Revision ID: 20261108_0014
Revises: 20261108_0013
Create Date: 2026-11-08 13:00:00

The signal pass compared reported EPS with "actual * 0.9" as the estimate, so every company with
positive EPS got an 11% beat. No real consensus estimates were ever used; these rows carry no
information and fed the verdict, the signal feed and recommendations.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261108_0014'
down_revision: str | None = '20261108_0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM signals WHERE signal_type = 'earnings_surprise'")


def downgrade() -> None:
    pass  # the deleted rows were invented; nothing to restore
