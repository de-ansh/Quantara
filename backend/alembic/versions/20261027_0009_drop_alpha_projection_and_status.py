"""drop invented stock fields; clear scores with no analysis behind them

Revision ID: 20261027_0009
Revises: 20261023_0008
Create Date: 2026-10-27 10:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261027_0009'
down_revision: str | None = '20261023_0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('stocks', 'alpha_projection')
    op.drop_column('stocks', 'status')
    # Seeded scores were hand-typed; keep only those backed by a research report.
    # Risk scores are recomputed from real data by the background refresh.
    op.execute(
        "UPDATE stocks SET risk_score = NULL, research_score = NULL "
        "WHERE ticker NOT IN (SELECT ticker FROM research_reports)"
    )


def downgrade() -> None:
    # Cleared scores are not restored.
    op.add_column('stocks', sa.Column('status', sa.VARCHAR(length=20), nullable=True,
                                      comment='Signal trend status (up/down/neutral)'))
    op.add_column('stocks', sa.Column('alpha_projection', sa.VARCHAR(length=50), nullable=True,
                                      comment='Alpha projection percentage formatted'))
