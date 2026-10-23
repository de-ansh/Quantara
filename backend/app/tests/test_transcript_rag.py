"""Unit and integration tests for TranscriptProvider and RAG qualitative excerpt retrieval."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.providers.transcript import PRIMARY_TRANSCRIPTS, TranscriptProvider
from app.services.llm_orchestrator import LLMOrchestrator


class TestTranscriptProvider:
    @pytest.mark.asyncio
    async def test_fetch_transcript_primary(self):
        provider = TranscriptProvider()
        transcript = await provider.fetch_transcript("AAPL")

        assert transcript["ticker"] == "AAPL"
        assert transcript["quarter"] == "Q4"
        assert transcript["year"] == 2024
        assert "executive_remarks" in transcript["sections"]
        assert "guidance" in transcript["sections"]
        assert "financial_review" in transcript["sections"]
        assert "qa_session" in transcript["sections"]
        assert "Tim Cook" in transcript["full_text"]

    @pytest.mark.asyncio
    async def test_fetch_transcript_unknown_ticker_returns_none(self):
        """No fabricated management commentary for tickers without a transcript."""
        provider = TranscriptProvider()
        assert await provider.fetch_transcript("PLTR", quarter="Q2", year=2024) is None

    def test_chunk_transcript_sliding_window(self):
        provider = TranscriptProvider()
        sample_data = PRIMARY_TRANSCRIPTS["AAPL"]

        chunks = provider.chunk_transcript(sample_data, chunk_size=300, chunk_overlap=50)

        assert len(chunks) >= 4
        # Verify chunk structure
        for c in chunks:
            assert "chunk_id" in c
            assert "text" in c
            assert len(c["text"]) > 0
            assert "section" in c
            assert "token_estimate" in c
            assert c["token_estimate"] > 0

    @pytest.mark.asyncio
    async def test_generate_embeddings_deterministic(self):
        provider = TranscriptProvider()
        texts = [
            "Apple reported revenue of $94.9 billion for the September quarter.",
            "Gross margin was 46.2%, at the high end of our guidance range.",
        ]

        embeddings = await provider.generate_embeddings(texts)

        assert len(embeddings) == 2
        for emb in embeddings:
            assert len(emb) == 1536
            # Verify unit vector normalization
            norm = np.linalg.norm(np.array(emb, dtype=np.float32))
            assert norm == pytest.approx(1.0, rel=1e-4)

    def test_retrieve_top_k_ranking(self):
        provider = TranscriptProvider()
        chunks = [
            {
                "chunk_id": 0,
                "text": "Tim Cook discussed iPhone 16 launch, hardware shipments, and Apple Intelligence adoption.",
                "section": "executive_remarks",
                "speaker": "Tim Cook",
                "token_estimate": 25,
            },
            {
                "chunk_id": 1,
                "text": "Gross margin was 46.2% with Services gross margin expanding to 74.0%. Guidance projects 46.5%.",
                "section": "guidance",
                "speaker": "Luca Maestri",
                "token_estimate": 25,
            },
            {
                "chunk_id": 2,
                "text": "Capital expenditures focused on Private Cloud Compute server clusters and custom silicon.",
                "section": "qa_session",
                "speaker": "Tim Cook",
                "token_estimate": 20,
            },
        ]

        embeddings = [
            provider._compute_deterministic_embedding(c["text"]) for c in chunks
        ]

        # Query targeting margin and guidance
        query = "guidance gross margin target projection"
        top_excerpts = provider.retrieve_top_k(query=query, chunks=chunks, chunk_embeddings=embeddings, k=2)

        assert len(top_excerpts) == 2
        # The margin/guidance chunk should rank #1
        assert top_excerpts[0]["chunk_id"] == 1
        assert top_excerpts[0]["section"] == "guidance"
        assert top_excerpts[0]["similarity_score"] > top_excerpts[1]["similarity_score"]

    @pytest.mark.asyncio
    async def test_openai_embedding_mocked(self):
        provider = TranscriptProvider(openai_api_key="sk-real-valid-key-for-test-mocking")

        mock_embedding_response = MagicMock()
        item1 = MagicMock()
        item1.embedding = [0.1] * 1536
        mock_embedding_response.data = [item1]

        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_embedding_response)
            mock_client_cls.return_value = mock_client

            embeddings = await provider.generate_embeddings(["Sample text for embedding test"])
            assert len(embeddings) == 1
            assert len(embeddings[0]) == 1536


class TestLLMOrchestratorTranscriptRAG:
    @pytest.mark.asyncio
    async def test_process_transcripts_rag_node(self):
        with patch("app.services.llm_orchestrator.ChatOpenAI"):
            orchestrator = LLMOrchestrator()

        state = {
            "ticker": "NVDA",
            "raw_data": {},
            "computed_metrics": {},
            "risk_classification": {"risk_band": "growth"},
            "structured_analysis": {},
            "validation_errors": [],
            "retry_count": 0,
            "final_output": None,
            "db": None,
            "openai_api_key": None,
            "sec_user_agent": None,
            "transcripts": [],
            "transcript_chunks": [],
            "qualitative_excerpts": [],
        }

        updated_state = await orchestrator._process_transcripts_rag(state)

        assert len(updated_state["transcripts"]) == 1
        assert updated_state["transcripts"][0]["ticker"] == "NVDA"
        assert len(updated_state["transcript_chunks"]) > 0
        assert len(updated_state["qualitative_excerpts"]) <= 3
        assert len(updated_state["qualitative_excerpts"]) > 0

        # Verify excerpt fields
        excerpt = updated_state["qualitative_excerpts"][0]
        assert "text" in excerpt
        assert "section" in excerpt
        assert "similarity_score" in excerpt
