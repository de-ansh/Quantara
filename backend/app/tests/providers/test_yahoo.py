"""Unit tests for Yahoo Finance data provider."""
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from app.providers.yahoo import YahooFinanceProvider

class TestYahooFinanceProvider:
    """Test suite for YahooFinanceProvider."""

    @pytest.fixture
    def provider(self):
        """Provider fixture."""
        return YahooFinanceProvider(max_retries=1)

    @pytest.fixture
    def mock_df(self):
        """Mock data fixture."""
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        data = {
            "Open": [100.0 + i for i in range(10)],
            "High": [105.0 + i for i in range(10)],
            "Low": [95.0 + i for i in range(10)],
            "Close": [102.0, 104.0, 101.0, 105.0, 108.0, 107.0, 110.0, 112.0, 115.0, 114.0],
            "Volume": [1000 * i for i in range(10)],
            "Dividends": [0.0] * 10
        }
        return pd.DataFrame(data, index=dates)

    @pytest.fixture
    def mock_benchmark_df(self):
        """Mock benchmark data fixture."""
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        data = {
            "Close": [3900, 3920, 3910, 3930, 3950, 3940, 3960, 3980, 4000, 3990]
        }
        return pd.DataFrame(data, index=dates)

    @patch("yfinance.Ticker")
    @pytest.mark.asyncio
    async def test_get_historical_data_success(self, mock_ticker, provider, mock_df):
        """Test successful data retrieval."""
        instance = mock_ticker.return_value
        instance.history.return_value = mock_df
        
        df = await provider.get_historical_data("AAPL", start_date="2023-01-01", end_date="2023-01-10")
        
        assert not df.empty
        assert len(df) == 10
        assert "Close" in df.columns
        instance.history.assert_called_once()

    @patch("yfinance.Ticker")
    @pytest.mark.asyncio
    async def test_get_historical_data_retry(self, mock_ticker, provider, mock_df):
        """Test data retrieval with retries."""
        instance = mock_ticker.return_value
        # Raise exception first, then return data
        instance.history.side_effect = [Exception("API Error"), mock_df]
        
        df = await provider.get_historical_data("AAPL")
        
        assert not df.empty
        assert instance.history.call_count == 2

    def test_compute_metrics(self, provider, mock_df, mock_benchmark_df):
        """Test metrics computation."""
        metrics = provider.compute_metrics(mock_df, mock_benchmark_df)
        
        assert "historical_volatility" in metrics
        assert "max_drawdown" in metrics
        assert "total_return" in metrics
        assert "beta" in metrics
        
        # Verify specific calculations (approximate)
        assert metrics["total_return"] > 0
        assert metrics["max_drawdown"] <= 0
        assert isinstance(metrics["beta"], float)

    def test_compute_metrics_empty(self, provider):
        """Test metrics computation with empty data."""
        metrics = provider.compute_metrics(pd.DataFrame())
        assert metrics == {}

    def test_compute_metrics_no_benchmark(self, provider, mock_df):
        """Test metrics computation without benchmark."""
        metrics = provider.compute_metrics(mock_df)
        assert "beta" in metrics
        assert metrics["beta"] is None
