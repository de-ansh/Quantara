"""ROCE and 3-year growth from annual statements (Yahoo gives four fiscal years).

ROCE = EBIT / capital employed (total assets - current liabilities), latest year.
Growth = compound annual growth from three years earlier to the latest year; only when both ends
are positive, since a CAGR across a loss is meaningless. Banks and other lenders report no EBIT or
current liabilities, so their ROCE stays empty rather than being guessed.
"""

import asyncio
from datetime import timedelta
from typing import Any

import pandas as pd
import yfinance as yf
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.stock import Stock

logger = get_logger(__name__)

STATEMENTS_MAX_AGE = timedelta(days=7)  # annual figures change once a year
STATEMENTS_PER_PASS = 50  # ~500 tracked stocks refresh within a few hours, without a burst on Yahoo
RETRY_AFTER = timedelta(days=1)  # Yahoo returned nothing (often rate limiting); try again tomorrow
PAUSE_SECONDS = 1.0


def _latest_first(frame: pd.DataFrame, row: str) -> list[float | None]:
    """A statement row's yearly values, newest first; None where missing."""
    if frame is None or frame.empty or row not in frame.index:
        return []
    series = frame.loc[row]
    series = series[sorted(series.index, reverse=True)]
    return [None if pd.isna(v) else float(v) for v in series.tolist()]


def _cagr_3y(values: list[float | None]) -> float | None:
    if len(values) < 4 or values[0] is None or values[3] is None or values[0] <= 0 or values[3] <= 0:
        return None
    yearly: float = (values[0] / values[3]) ** (1 / 3)
    return round((yearly - 1) * 100, 2)


def statement_metrics(income: pd.DataFrame, balance: pd.DataFrame) -> dict[str, float | None]:
    ebit = _latest_first(income, "EBIT")
    assets = _latest_first(balance, "Total Assets")
    current_liabilities = _latest_first(balance, "Current Liabilities")
    roce = None
    latest_ebit, latest_assets, latest_cl = (ebit or [None])[0], (assets or [None])[0], (current_liabilities or [None])[0]
    if latest_ebit is not None and latest_assets is not None and latest_cl is not None:
        capital_employed = latest_assets - latest_cl
        if capital_employed > 0:
            roce = round(latest_ebit / capital_employed * 100, 2)
    return {
        "roce_pct": roce,
        "revenue_cagr_3y_pct": _cagr_3y(_latest_first(income, "Total Revenue")),
        "profit_cagr_3y_pct": _cagr_3y(_latest_first(income, "Net Income")),
    }


def fetch_statement_metrics(ticker: str) -> dict[str, Any] | None:
    """None when Yahoo sends no statements at all: when rate limited it returns empty tables, not errors."""
    try:
        stock = yf.Ticker(ticker)
        income, balance = stock.income_stmt, stock.balance_sheet
        if income.empty and balance.empty:
            return None
        return statement_metrics(income, balance)
    except Exception as e:
        logger.warning(f"Statements lookup failed for {ticker}: {e}")
        return None


async def refresh_statements(db: AsyncSession, limit: int = STATEMENTS_PER_PASS) -> int:
    """Refresh ROCE/growth for up to `limit` stocks not updated within a week, oldest first."""
    cutoff = utcnow() - STATEMENTS_MAX_AGE
    due = (await db.execute(
        select(Stock)
        .where(or_(Stock.statements_updated_at.is_(None), Stock.statements_updated_at < cutoff))
        .order_by(Stock.statements_updated_at.asc().nulls_first())
        .limit(limit)
    )).scalars().all()
    updated = 0
    for stock in due:
        metrics = await asyncio.to_thread(fetch_statement_metrics, stock.ticker)
        if metrics is None:
            # Stamped as due again in a day, so a throttled or statement-less stock isn't retried every pass
            stock.statements_updated_at = utcnow() - STATEMENTS_MAX_AGE + RETRY_AFTER
        else:
            stock.statements_updated_at = utcnow()
            for field, value in metrics.items():
                setattr(stock, field, value)
            updated += 1
        await asyncio.sleep(PAUSE_SECONDS)
    await db.commit()
    return updated
