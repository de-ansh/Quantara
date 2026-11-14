"""The verdict backtest must only ever see data that was public on the replay date."""

from datetime import date

import pandas as pd

from app.models.stock import Stock
from app.services.backtest import (
    Replay,
    forward_return,
    fundamentals_at,
    promoter_change,
    stock_as_of,
    summarize,
)

FY = [pd.Timestamp(f"{y}-03-31") for y in (2025, 2024, 2023, 2022)]  # Yahoo order: newest first
INCOME = pd.DataFrame(
    dict(zip(FY, [
        {"Total Revenue": 160.0, "Net Income": 32.0, "EBIT": 40.0},
        {"Total Revenue": 100.0, "Net Income": 20.0, "EBIT": 25.0},
        {"Total Revenue": 90.0, "Net Income": 18.0, "EBIT": 22.0},
        {"Total Revenue": 80.0, "Net Income": 16.0, "EBIT": 20.0},
    ], strict=True))
)
BALANCE = pd.DataFrame(
    {fy: {"Stockholders Equity": 100.0, "Total Debt": 20.0, "Total Assets": 200.0, "Current Liabilities": 40.0}
     for fy in FY}
)


def test_fundamentals_use_only_results_already_filed():
    # 30 Apr 2025: FY25 (ended 31 Mar) isn't filed yet, so FY24 is the latest year
    before = fundamentals_at(INCOME, BALANCE, date(2025, 4, 30))
    assert before["fiscal_year"] == 2024 and before["revenue_growth_pct"] == 11.11
    assert before["revenue_cagr_3y_pct"] is None  # FY21 isn't in the data
    after = fundamentals_at(INCOME, BALANCE, date(2025, 6, 30))
    assert after["fiscal_year"] == 2025 and after["revenue_growth_pct"] == 60.0
    assert after["roe_pct"] == 32.0 and after["roce_pct"] == 25.0 and after["debt_to_equity"] == 0.2
    assert after["revenue_cagr_3y_pct"] == 25.99 and after["profit_margin_pct"] == 20.0
    assert fundamentals_at(INCOME, BALANCE, date(2022, 1, 1)) == {}


def test_prices_and_returns_never_look_past_the_data():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.to_datetime(["2025-06-27", "2025-09-29", "2025-12-29"]))
    # 30 Jun is a holiday-ish gap: the 27 Jun close is used
    assert forward_return(prices, date(2025, 6, 30), 91, last_day=date(2025, 12, 31)) == 10.0
    # A horizon that ends after the last price is not scored, rather than scored on a stale price
    assert forward_return(prices, date(2025, 6, 30), 365, last_day=date(2025, 12, 31)) is None


def test_promoter_change_waits_for_disclosure_and_needs_consecutive_quarters():
    holdings = {date(2025, 3, 31): 50.0, date(2025, 6, 30): 52.5, date(2024, 6, 30): 40.0}
    assert promoter_change(holdings, date(2025, 7, 10)) is None  # June quarter not disclosed yet; gap to 2024
    assert promoter_change(holdings, date(2025, 7, 31)) == 2.5


def test_stock_as_of_values_pe_with_the_price_then():
    idx = pd.to_datetime(["2024-06-28", "2025-06-30"])
    close = pd.Series([400.0, 500.0], index=idx)
    dividends = pd.Series([10.0], index=pd.to_datetime(["2025-02-01"]))
    current = Stock(ticker="X.NS", name="X", price=1000.0, market_cap=1000.0 * 0.32)  # 0.32 shares
    past = stock_as_of(current, INCOME, BALANCE, close, close, dividends, {}, date(2025, 6, 30))
    assert past is not None and past.price == 500.0
    assert past.pe_ratio == 5.0  # 500 x 0.32 shares / 32 profit
    assert past.return_1y_pct == 25.0 and past.dividend_yield_pct == 2.0
    assert stock_as_of(current, INCOME, BALANCE, close, close, dividends, {}, date(2023, 1, 1)) is None


def test_summary_groups_by_verdict():
    rows = [
        Replay("A", date(2025, 6, 30), "Buy", 75.0, {"3m": 20.0, "6m": None, "12m": None}, {"3m": 10.0, "6m": None, "12m": None}),
        Replay("B", date(2025, 6, 30), "Avoid", 30.0, {"3m": 0.0, "6m": None, "12m": None}, {"3m": -10.0, "6m": None, "12m": None}),
    ]
    text = summarize(rows)
    assert "### 3m" in text and "### 6m" not in text
    assert "| Buy | 1 | +20.0% | +10.0 pp | +10.0 pp | 100% | +10.0 pp |" in text
    assert "| Avoid | 1 | +0.0% | -10.0 pp | -10.0 pp | 0% | -10.0 pp |" in text


def test_a_stock_that_never_paid_a_dividend_still_replays():
    close = pd.Series([400.0, 500.0], index=pd.to_datetime(["2024-06-28", "2025-06-30"]))
    none_paid = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    current = Stock(ticker="X.NS", name="X", price=1000.0, market_cap=320.0)
    past = stock_as_of(current, INCOME, BALANCE, close, close, none_paid, {}, date(2025, 6, 30))
    assert past is not None and past.dividend_yield_pct is None
