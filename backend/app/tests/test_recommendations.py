"""Tests for Recommendations API and Engine."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.recommendations import get_recommendations
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.services.recommendation_engine import RecommendationEngine


@pytest.fixture
def mock_current_user():
    return {
        "id": "1",
        "email": "analyst@quantara.com",
        "risk_level": "Moderate",
        "volatility_tolerance": 60.0,
    }


@pytest.fixture
def sample_stocks():
    return [
        Stock(
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            risk_score=50.0,
            research_score=85.0,
        ),
        Stock(
            ticker="MSFT",
            name="Microsoft Corp.",
            sector="Technology",
            risk_score=45.0,
            research_score=90.0,
        ),
        Stock(
            ticker="TSLA",
            name="Tesla Inc.",
            sector="Consumer Discretionary",
            risk_score=75.0,
            research_score=65.0,
        ),
    ]


@pytest.mark.asyncio
async def test_get_recommendations_with_db_stocks(mock_current_user, sample_stocks):
    """Test get_recommendations dynamically ranks DB stocks and persists to recommendations table."""
    mock_db = AsyncMock()

    # Setup mock executes
    # 1st execute: select(Stock)
    mock_stock_result = MagicMock()
    mock_stock_result.scalars().all.return_value = sample_stocks

    # 2nd execute: select(Signal.ticker, func.avg(Signal.strength)).group_by(Signal.ticker)
    mock_sig_result = MagicMock()
    mock_sig_result.all.return_value = [("AAPL", 80.0), ("MSFT", 70.0)]

    # 3rd execute: select(Recommendation) for active previous recommendations
    mock_active_prev = MagicMock()
    mock_active_prev.scalars().all.return_value = []

    mock_db.execute.side_effect = [
        mock_stock_result,
        mock_sig_result,
        mock_active_prev,
    ]

    response = await get_recommendations(
        current_user=mock_current_user,
        db=mock_db,
        limit=5,
    )

    assert response.total_count > 0
    assert response.user_risk_level == "Moderate"
    assert len(response.recommendations) > 0

    # Ensure recommendations were added to DB
    assert mock_db.add.called
    added_recs = [call[0][0] for call in mock_db.add.call_args_list]
    assert len(added_recs) == len(response.recommendations)
    for rec in added_recs:
        assert isinstance(rec, Recommendation)
        assert rec.user_id == 1
        assert rec.is_active is True
        assert rec.final_score > 0

    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_get_recommendations_empty_db(mock_current_user):
    """Test get_recommendations handles empty stock database gracefully."""
    mock_db = AsyncMock()

    mock_stock_result = MagicMock()
    mock_stock_result.scalars().all.return_value = []
    mock_db.execute.return_value = mock_stock_result

    response = await get_recommendations(
        current_user=mock_current_user,
        db=mock_db,
        limit=5,
    )

    assert response.total_count == 0
    assert response.recommendations == []
    assert response.user_risk_level == "Moderate"


@pytest.mark.asyncio
async def test_get_recommendations_deactivates_stale_records(mock_current_user, sample_stocks):
    """Test that previous active recommendations for the user are marked inactive."""
    mock_db = AsyncMock()

    mock_stock_result = MagicMock()
    mock_stock_result.scalars().all.return_value = sample_stocks

    mock_sig_result = MagicMock()
    mock_sig_result.all.return_value = []

    stale_rec = Recommendation(
        user_id=1,
        ticker="OLD",
        final_score=50.0,
        research_score=50.0,
        signal_score=50.0,
        risk_alignment_score=50.0,
        macro_fit_score=50.0,
        explanation_text="Old",
        reasoning_metadata={},
        is_active=True,
    )
    mock_active_prev = MagicMock()
    mock_active_prev.scalars().all.return_value = [stale_rec]

    mock_db.execute.side_effect = [
        mock_stock_result,
        mock_sig_result,
        mock_active_prev,
    ]

    response = await get_recommendations(
        current_user=mock_current_user,
        db=mock_db,
        limit=5,
    )

    assert stale_rec.is_active is False
    assert mock_db.commit.called


def test_recommendation_engine_alignment():
    """Test recommendation engine risk alignment and scoring calculation."""
    engine = RecommendationEngine()

    # Conservative user with low-risk stock
    score_cons = engine.calculate_risk_alignment_score(
        stock_risk_score=20.0,
        user_risk_level="Conservative",
        user_volatility_tolerance=30.0,
    )
    assert score_cons > 70.0

    # Conservative user with aggressive stock
    score_mismatch = engine.calculate_risk_alignment_score(
        stock_risk_score=85.0,
        user_risk_level="Conservative",
        user_volatility_tolerance=30.0,
    )
    assert score_mismatch < score_cons
