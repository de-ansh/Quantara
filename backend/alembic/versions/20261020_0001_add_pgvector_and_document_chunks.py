"""baseline schema: pgvector extension and all model tables

Revision ID: 20261020_0001
Revises: 
Create Date: 2026-10-20 12:45:00

"""
from typing import Sequence, Union

from alembic import op

from app.core.database import Base
import app.models  # noqa: F401  registers every table on Base.metadata


# revision identifiers, used by Alembic.
revision: str = "20261020_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # Baseline: no earlier revision created users/stocks/etc., which document_chunks FKs into.
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
