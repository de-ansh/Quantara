"""Tests for pgvector DocumentChunk model and transcript vector store operations."""

import pytest
import numpy as np
from sqlalchemy import select

from app.models.document_chunk import DocumentChunk
from app.models.stock import Stock
from app.providers.transcript import TranscriptProvider


@pytest.mark.asyncio
async def test_create_and_query_document_chunk(db_session):
    # 1. Seed stock
    stock = Stock(
        ticker="NVDA",
        name="NVIDIA Corporation",
        sector="Technology",
        risk_score=75.0,
        research_score=85.0,
        price="$120.00",
        market_cap="2.8T",
    )
    db_session.add(stock)
    await db_session.flush()

    # 2. Create deterministic 1536-dim vector
    provider = TranscriptProvider()
    vec1 = provider._compute_deterministic_embedding("Accelerated computing and data center revenue surged 200%.")
    assert len(vec1) == 1536

    # 3. Insert DocumentChunk
    chunk = DocumentChunk(
        ticker="NVDA",
        document_type="earnings_call",
        period="Q3 2024",
        chunk_index=0,
        chunk_text="Accelerated computing and data center revenue surged 200%.",
        embedding=vec1,
        token_count=12,
        data={"speaker": "Jensen Huang", "section": "prepared_remarks"},
    )
    db_session.add(chunk)
    await db_session.commit()

    # 4. Query chunk from db
    stmt = select(DocumentChunk).where(DocumentChunk.ticker == "NVDA")
    res = await db_session.execute(stmt)
    retrieved = res.scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.ticker == "NVDA"
    assert retrieved.document_type == "earnings_call"
    assert retrieved.period == "Q3 2024"
    assert "data center" in retrieved.chunk_text
    assert len(retrieved.embedding) == 1536


@pytest.mark.asyncio
async def test_pgvector_cosine_similarity_search(db_session):
    provider = TranscriptProvider()

    # Seed 2 distinct chunks
    stock = Stock(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        risk_score=25.0,
        research_score=80.0,
        price="$190.00",
        market_cap="2.9T",
    )
    db_session.add(stock)
    await db_session.flush()

    # Chunk A: iPhone services growth
    text_a = "Services revenue reached an all-time record of $23.1 billion with strong subscription growth."
    vec_a = provider._compute_deterministic_embedding(text_a)

    # Chunk B: Supply chain and manufacturing
    text_b = "Supply chain disruptions impacted hardware shipping lead times across APAC regions."
    vec_b = provider._compute_deterministic_embedding(text_b)

    chunk_a = DocumentChunk(
        ticker="AAPL",
        document_type="earnings_call",
        period="Q4 2023",
        chunk_index=0,
        chunk_text=text_a,
        embedding=vec_a,
        token_count=18,
    )
    chunk_b = DocumentChunk(
        ticker="AAPL",
        document_type="earnings_call",
        period="Q4 2023",
        chunk_index=1,
        chunk_text=text_b,
        embedding=vec_b,
        token_count=15,
    )
    db_session.add_all([chunk_a, chunk_b])
    await db_session.commit()

    # Query for subscription services
    query_text = "What is the subscription and services revenue performance?"
    query_vec = provider._compute_deterministic_embedding(query_text)

    # Execute pgvector search
    results = await provider.search_similar_chunks(
        db=db_session,
        query_embedding=query_vec,
        ticker="AAPL",
        top_k=2,
    )

    assert len(results) == 2
    # Chunk A should rank higher than Chunk B for services query
    assert "Services revenue" in results[0]["text"]
    assert results[0]["similarity_score"] >= results[1]["similarity_score"]


@pytest.mark.asyncio
async def test_store_and_search_chunks_end_to_end(db_session):
    provider = TranscriptProvider()

    raw_transcript = (
        "Good afternoon and welcome to Microsoft's conference call. "
        "Azure and cloud revenue grew 30 percent in constant currency driven by generative AI adoption. "
        "Operating margins expanded 200 basis points year over year."
    )

    # Chunk transcript
    chunks = provider.chunk_transcript(raw_transcript)
    assert len(chunks) > 0

    # Generate embeddings
    embeddings = await provider.generate_embeddings([c["text"] for c in chunks])
    assert len(embeddings) == len(chunks)

    # Store in pgvector table
    saved = await provider.store_chunks(
        db=db_session,
        ticker="MSFT",
        chunks=chunks,
        embeddings=embeddings,
        document_type="earnings_call",
        period="Q1 2024",
    )
    assert len(saved) == len(chunks)

    # Search for Azure and Cloud growth
    search_res = await provider.search_similar_chunks(
        db=db_session,
        query="cloud and azure growth rates",
        ticker="MSFT",
        top_k=1,
    )

    assert len(search_res) == 1
    assert search_res[0]["ticker"] == "MSFT"
    assert search_res[0]["similarity_score"] > 0.0
