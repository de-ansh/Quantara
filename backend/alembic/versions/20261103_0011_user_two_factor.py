"""two-factor login (TOTP) for users

Revision ID: 20261103_0011
Revises: 20261029_0010
Create Date: 2026-11-03 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261103_0011'
down_revision: str | None = '20261029_0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('totp_secret', sa.String(length=512), nullable=True))
    op.add_column(
        'users', sa.Column('totp_enabled', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column('users', sa.Column('totp_last_counter', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('totp_recovery_codes', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'totp_recovery_codes')
    op.drop_column('users', 'totp_last_counter')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')
