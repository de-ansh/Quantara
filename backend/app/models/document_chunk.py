"""Document chunk model for qualitative vector search."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentChunk(Base):
    """Document chunk model storing transcript & filing excerpts with vector embeddings."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker"), nullable=False, index=True
    )

    # Document classification
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="earnings_call, sec_10k, sec_10q, sec_8k, news",
    )
    period: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="e.g. Q4 2023, FY 2023"
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Sequential chunk index"
    )

    # Text & Vector Embedding
    chunk_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Raw text content of the chunk"
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536), nullable=False, comment="1536-dimensional OpenAI vector embedding"
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Estimated token count in chunk"
    )

    # Metadata (speakers, timestamps, sentiment scores, etc.)
    data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="Additional chunk-specific metadata"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_doc_chunk_ticker_doc_type", "ticker", "document_type"),
        Index("idx_doc_chunk_ticker_period", "ticker", "period"),
        Index(
            "idx_doc_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, ticker={self.ticker}, "
            f"type={self.document_type}, period={self.period}, index={self.chunk_index})>"
        )
