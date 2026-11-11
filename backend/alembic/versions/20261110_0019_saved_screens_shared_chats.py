"""Saved screener filters and shareable research chats

Revision ID: 20261110_0019
Revises: 20261110_0018
Create Date: 2026-11-10 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261110_0019'
down_revision: str | None = '20261110_0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'saved_screens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=False),
        sa.Column('sort', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'name', name='uq_saved_screen_user_name'),
    )
    op.create_index(op.f('ix_saved_screens_id'), 'saved_screens', ['id'])
    op.create_index(op.f('ix_saved_screens_user_id'), 'saved_screens', ['user_id'])
    op.create_table(
        'shared_chats',
        sa.Column('token', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('messages', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_shared_chats_user_id'), 'shared_chats', ['user_id'])


def downgrade() -> None:
    op.drop_table('shared_chats')
    op.drop_table('saved_screens')
