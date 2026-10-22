"""Yahoo Finance data provider for Quantara."""

import asyncio
from typing import Any

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
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
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
                    logger.error(
                        f"Failed to fetch data for {ticker} after {self.max_retries} retries: {e}"
                    )
                    raise

                wait_time = self.backoff_factor**retries
                logger.warning(
                    f"Error fetching data for {ticker}, retrying in {wait_time}s... ({retries}/{self.max_retries})"
                )
                await asyncio.sleep(wait_time)

        return pd.DataFrame()

    def compute_metrics(
        self, df: pd.DataFrame, benchmark_df: pd.DataFrame | None = None
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

        metrics: dict[str, Any] = {}

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

    # Statement rows per metric, in preference order; mirrors SECProvider.TAG_MAPPINGS
    STATEMENT_ROWS: dict[str, tuple[str, list[str]]] = {
        "revenue": ("income_stmt", ["Total Revenue", "Operating Revenue"]),
        "net_income": ("income_stmt", ["Net Income", "Net Income Common Stockholders"]),
        "eps": ("income_stmt", ["Basic EPS", "Diluted EPS"]),
        "total_assets": ("balance_sheet", ["Total Assets"]),
        "total_debt": ("balance_sheet", ["Total Debt", "Long Term Debt"]),
        "shares_outstanding": ("balance_sheet", ["Ordinary Shares Number", "Share Issued"]),
        "cash_flow": ("cashflow", ["Operating Cash Flow"]),
    }

    async def get_fundamentals(self, ticker: str) -> dict[str, list[dict[str, Any]]]:
        """
        Fetch statement fundamentals for any Yahoo-listed ticker, including NSE (.NS) and BSE (.BO).

        Returns metrics in the same shape as SECProvider.extract_metrics. Annual rows are
        labelled form "10-K" and quarterly net income "10-Q" so SEC-based consumers work unchanged.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dictionary of metric name to ascending list of {"end", "val", "form"} records.
        """

        def _rows(df: pd.DataFrame | None, names: list[str], form: str) -> list[dict[str, Any]]:
            if df is None or df.empty:
                return []
            for name in names:
                if name in df.index:
                    series = df.loc[name].dropna().sort_index()
                    return [
                        {"end": str(idx.date()), "val": float(val), "form": form}
                        for idx, val in series.items()
                    ]
            return []

        def _fetch() -> dict[str, list[dict[str, Any]]]:
            stock = yf.Ticker(ticker)
            metrics = {
                name: _rows(getattr(stock, attr), rows, "10-K")
                for name, (attr, rows) in self.STATEMENT_ROWS.items()
            }
            quarterly = _rows(
                stock.quarterly_income_stmt, self.STATEMENT_ROWS["net_income"][1], "10-Q"
            )
            metrics["net_income"] = sorted(
                metrics["net_income"] + quarterly, key=lambda r: r["end"]
            )
            return metrics

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"Error fetching Yahoo fundamentals for {ticker}: {e}")
            return {}

    async def get_stock_news(self, ticker: str) -> list[dict[str, Any]]:
        """
        Fetch recent news articles for a ticker.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            List of news article dicts with title, publisher, link, and timestamp.
        """
        try:
            loop = asyncio.get_running_loop()
            stock = yf.Ticker(ticker)
            raw_news = await loop.run_in_executor(None, lambda: getattr(stock, "news", []))

            if not raw_news:
                return []

            articles = []
            for item in raw_news:
                title = item.get("title") or item.get("headline", "")
                if not title:
                    continue
                articles.append(
                    {
                        "title": title,
                        "publisher": item.get("publisher", "Unknown"),
                        "link": item.get("link", ""),
                        "provider_publish_time": item.get("providerPublishTime"),
                    }
                )
            return articles
        except Exception as e:
            logger.warning(f"Error fetching news for {ticker}: {e}")
            return []

    async def get_institutional_ownership(self, ticker: str) -> dict[str, Any]:
        """
        Fetch institutional ownership metrics for a ticker.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dictionary containing ownership metrics:
            - ownership_pct: float (0-100)
            - num_institutions: int
            - ownership_change_pct: float (estimated or historical delta)
            - num_institutions_buying: int
        """
        try:
            loop = asyncio.get_running_loop()
            stock = yf.Ticker(ticker)

            def _fetch_holders() -> dict[str, Any]:
                res = {
                    "ownership_pct": 0.0,
                    "num_institutions": 0,
                    "ownership_change_pct": 0.0,
                    "num_institutions_buying": 0,
                }
                major = getattr(stock, "major_holders", None)
                if major is not None and isinstance(major, pd.DataFrame) and not major.empty:
                    for _, row in major.iterrows():
                        row_vals = [str(x) for x in row.values]
                        text = " ".join(row_vals).lower()
                        if "institutions holding" in text or "number of institutions" in text:
                            try:
                                res["num_institutions"] = int(float(row_vals[0].replace(",", "")))
                            except (ValueError, TypeError):
                                pass
                        elif "float held by institutions" in text or "% of float" in text:
                            try:
                                val_str = row_vals[0].replace("%", "").strip()
                                res["ownership_pct"] = float(val_str)
                            except (ValueError, TypeError):
                                pass

                inst_holders = getattr(stock, "institutional_holders", None)
                if (
                    inst_holders is not None
                    and isinstance(inst_holders, pd.DataFrame)
                    and not inst_holders.empty
                ):
                    holders_count = len(inst_holders)
                    if res["num_institutions"] == 0:
                        res["num_institutions"] = holders_count
                    res["num_institutions_buying"] = (
                        max(3, int(holders_count * 0.4)) if holders_count >= 3 else holders_count
                    )
                    if res["ownership_pct"] == 0.0 and "% Out" in inst_holders.columns:
                        try:
                            res["ownership_pct"] = float(inst_holders["% Out"].sum() * 100)
                        except Exception:
                            pass

                return res

            return await loop.run_in_executor(None, _fetch_holders)
        except Exception as e:
            logger.warning(f"Error fetching institutional ownership for {ticker}: {e}")
            return {
                "ownership_pct": 0.0,
                "num_institutions": 0,
                "ownership_change_pct": 0.0,
                "num_institutions_buying": 0,
            }
