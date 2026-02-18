"""Yahoo Finance data provider for Quantara."""
import asyncio
import time
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from app.core.logging import get_logger

logger = get_logger(__name__)

class YahooFinanceProvider:
    """
    Yahoo Finance data provider.
    
    Fetches historical data and computes deterministic financial metrics.
    """

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        """
        Initialize the provider.
        
        Args:
            max_retries: Maximum number of retries for API calls.
            backoff_factor: Backoff factor for retries.
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def get_historical_data(
        self, 
        ticker: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data and dividends.
        
        Args:
            ticker: Stock ticker symbol.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            interval: Data interval (e.g., "1d", "1wk", "1mo").
            
        Returns:
            Pandas DataFrame with historical data.
        """
        logger.info(f"Fetching historical data for {ticker} from {start_date} to {end_date}")
        
        retries = 0
        while retries <= self.max_retries:
            try:
                # yfinance is blocking, but we can run it in a thread pool if needed.
                # For now, we'll call it directly as requested.
                stock = yf.Ticker(ticker)
                df = stock.history(start=start_date, end=end_date, interval=interval)
                
                if df.empty:
                    logger.warning(f"No data found for {ticker}")
                    return pd.DataFrame()
                
                # Ensure all required columns are present
                required_columns = ["Open", "High", "Low", "Close", "Volume", "Dividends"]
                for col in required_columns:
                    if col not in df.columns:
                        df[col] = np.nan
                        
                return df
                
            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(f"Failed to fetch data for {ticker} after {self.max_retries} retries: {e}")
                    raise
                
                wait_time = self.backoff_factor ** retries
                logger.warning(f"Error fetching data for {ticker}, retrying in {wait_time}s... ({retries}/{self.max_retries})")
                await asyncio.sleep(wait_time)
        
        return pd.DataFrame()

    def compute_metrics(
        self, 
        df: pd.DataFrame, 
        benchmark_df: Optional[pd.DataFrame] = None
    ) -> dict[str, Any]:
        """
        Compute deterministic financial metrics from historical data.
        
        Metrics include:
        - Annualized Volatility
        - Max Drawdown
        - Rolling Returns (Cumulative)
        - Beta (if benchmark_df is provided)
        
        Args:
            df: Historical data DataFrame (must contain 'Close' or 'Adj Close').
            benchmark_df: Benchmark historical data (e.g., ^GSPC).
            
        Returns:
            Dictionary of computed metrics.
        """
        if df.empty:
            return {}

        # Use 'Close' if 'Adj Close' is not available (yfinance.history returns Adj Close as 'Close' by default)
        price_col = "Close"
        returns = df[price_col].pct_change().dropna()
        
        if returns.empty:
            return {}

        metrics = {}

        # 1. Historical Volatility (Annualized)
        # Assuming 252 trading days for daily data
        volatility = returns.std() * np.sqrt(252)
        metrics["historical_volatility"] = float(volatility)

        # 2. Max Drawdown
        cumulative_returns = (1 + returns).cumprod()
        peak = cumulative_returns.cummax()
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown = drawdown.min()
        metrics["max_drawdown"] = float(max_drawdown)

        # 3. Rolling Returns (latest cumulative return)
        metrics["total_return"] = float(cumulative_returns.iloc[-1] - 1)
        
        # 4. Beta vs S&P 500
        if benchmark_df is not None and not benchmark_df.empty:
            benchmark_returns = benchmark_df["Close"].pct_change().dropna()
            
            # Align returns and benchmark returns
            combined = pd.concat([returns, benchmark_returns], axis=1).dropna()
            combined.columns = ["asset", "benchmark"]
            
            if not combined.empty:
                covariance = combined.cov().iloc[0, 1]
                benchmark_variance = combined["benchmark"].var()
                beta = covariance / benchmark_variance if benchmark_variance != 0 else np.nan
                metrics["beta"] = float(beta)
            else:
                metrics["beta"] = None
        else:
            metrics["beta"] = None

        return metrics
