"""research_score now means outlook; clear the old confidence-based values

Revision ID: 20261108_0013
Revises: 20261107_0012
Create Date: 2026-11-08 12:00:00

Until now stocks.research_score held the report's confidence_score (data completeness), which
the verdict and recommendations read as a bullish signal. It now holds the confidence-weighted
outlook; stocks get a new value the next time their research report is generated.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261108_0013'
down_revision: str | None = '20261107_0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE stocks SET research_score = NULL")


def downgrade() -> None:
    # The old values were the reports' confidence scores, still stored on research_reports
    op.execute(
        "UPDATE stocks SET research_score = r.confidence_score FROM research_reports r WHERE r.ticker = stocks.ticker"
    )
