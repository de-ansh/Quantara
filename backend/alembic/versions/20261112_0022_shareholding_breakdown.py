"""Institutional split of each quarter's shareholding pattern

Revision ID: 20261112_0022
Revises: 20261112_0021
Create Date: 2026-11-12 08:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261112_0022'
down_revision: str | None = '20261112_0021'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    ('fii_pct', sa.Float(), 'Foreign institutions (FPIs etc.)'),
    ('dii_pct', sa.Float(), 'Domestic institutions, incl. mutual funds'),
    ('mf_pct', sa.Float(), 'Mutual funds (part of DII)'),
    ('retail_pct', sa.Float(), 'Non-institutional public'),
    ('shareholders', sa.BigInteger(), None),
]


def upgrade() -> None:
    for name, type_, comment in COLUMNS:
        op.add_column('shareholdings', sa.Column(name, type_, nullable=True, comment=comment))


def downgrade() -> None:
    for name, _, _ in reversed(COLUMNS):
        op.drop_column('shareholdings', name)
