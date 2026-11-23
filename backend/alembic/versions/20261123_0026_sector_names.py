"""Map Yahoo's raw sector names, saved by the research pipeline, to the app's

Revision ID: 20261123_0026
Revises: 20261120_0025
Create Date: 2026-11-23 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20261123_0026'
down_revision: str | None = '20261120_0025'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same as price_service.YAHOO_SECTORS, copied so the migration doesn't change if that does
NAMES = {
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Financial Services": "Financials",
    "Basic Materials": "Materials",
}


def upgrade() -> None:
    for yahoo, app in NAMES.items():
        op.execute(sa.text("UPDATE stocks SET sector = :app WHERE sector = :yahoo").bindparams(app=app, yahoo=yahoo))


def downgrade() -> None:
    pass  # the raw names were never wanted; nothing to restore
