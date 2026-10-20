"""add pgvector extension and document chunks table

Revision ID: 20261020_0001
Revises: 
Create Date: 2026-10-20 12:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "20261020_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"], name="fk_document_chunks_ticker"),
    )

    # 3. Create indices
    op.create_index("ix_document_chunks_id", "document_chunks", ["id"])
    op.create_index("ix_document_chunks_ticker", "document_chunks", ["ticker"])
    op.create_index("ix_document_chunks_document_type", "document_chunks", ["document_type"])
    op.create_index("ix_document_chunks_created_at", "document_chunks", ["created_at"])
    op.create_index(
        "idx_doc_chunk_ticker_doc_type",
        "document_chunks",
        ["ticker", "document_type"],
    )
    op.create_index(
        "idx_doc_chunk_ticker_period",
        "document_chunks",
        ["ticker", "period"],
    )
    op.create_index(
        "idx_doc_chunk_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_doc_chunk_embedding", table_name="document_chunks")
    op.drop_index("idx_doc_chunk_ticker_period", table_name="document_chunks")
    op.drop_index("idx_doc_chunk_ticker_doc_type", table_name="document_chunks")
    op.drop_index("ix_document_chunks_created_at", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_type", table_name="document_chunks")
    op.drop_index("ix_document_chunks_ticker", table_name="document_chunks")
    op.drop_index("ix_document_chunks_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
