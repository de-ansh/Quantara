"""Replay the numbers-only Buy/Hold/Avoid call (`stock_call.data_call`) on past dates and score it.

On each replay date the call sees only what was public then: the latest annual statements filed by
that date, prices up to that date, and promoter holdings already disclosed. It is then judged on the
next 3, 6 and 12 months' total return against the NIFTY 50 and against the average stock replayed.

Known gaps, which make this an estimate rather than a proof:
- Survivorship: the universe is today's Nifty 500, so stocks that collapsed and dropped out are missing.
  Comparing groups with each other (Buy vs Hold vs Avoid) is fairer than comparing them with the index.
- Risk score and signals are not rebuilt (no history), so they never move a past call.
- P/E uses today's share count, so dilution or buybacks since then shift it a little.

Run: uv run python -m app.services.backtest [--limit N] [--cache DIR] [--csv FILE]
"""

import argparse
import asyncio
import pickle
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import TypeVar, cast

import pandas as pd
import yfinance as yf
from sqlalchemy import select

from app.models.shareholding import Shareholding
from app.models.stock import Stock
from app.services.stock_call import data_call

REPLAY_DATES = [date(2023, 6, 30), date(2024, 6, 30), date(2025, 6, 30), date(2026, 6, 30)]
RESULTS_LAG = timedelta(days=60)  # annual results (March year-end) must be filed by the end of May
HOLDING_LAG = timedelta(days=21)  # shareholding is disclosed within 21 days of the quarter end
HORIZONS = {"3m": 91, "6m": 182, "12m": 365}
BENCHMARK = "^NSEI"
T = TypeVar("T")
PRICE_GAP = timedelta(days=7)  # a replay or horizon date may fall on a holiday; use the last close before it


@dataclass
class Replay:
    ticker: str
    as_of: date
    verdict: str
    score: float | None
    returns: dict[str, float | None]  # horizon -> total return %
    excess: dict[str, float | None]  # horizon -> return minus the NIFTY 50's, percentage points


def _yearly(frame: pd.DataFrame | None, row: str) -> dict[date, float]:
    """A statement row as {fiscal year end: value}, skipping blanks."""
    if frame is None or frame.empty or row not in frame.index:
        return {}
    return {pd.Timestamp(k).date(): float(v) for k, v in frame.loc[row].items() if pd.notna(v)}


def fundamentals_at(income: pd.DataFrame, balance: pd.DataFrame, as_of: date) -> dict[str, float | None]:
    """Ratios from the newest fiscal year whose results were public on `as_of` (never a later one)."""
    known = as_of - RESULTS_LAG
    revenue, profit, ebit = (_yearly(income, r) for r in ("Total Revenue", "Net Income", "EBIT"))
    equity, debt = _yearly(balance, "Stockholders Equity"), _yearly(balance, "Total Debt")
    assets, current = _yearly(balance, "Total Assets"), _yearly(balance, "Current Liabilities")
    years = sorted((y for y in revenue.keys() | profit.keys() if y <= known), reverse=True)
    if not years:
        return {}
    fy = years[0]

    def ratio(a: float | None, b: float | None, scale: float = 100.0) -> float | None:
        return round(a / b * scale, 2) if a is not None and b else None

    def growth(series: dict[date, float], back: int) -> float | None:
        then = [y for y in sorted(series, reverse=True) if y <= fy]
        if len(then) <= back or then[0] != fy:
            return None
        new, old = series[then[0]], series[then[back]]
        if new <= 0 or old <= 0:
            return None  # growth across a loss is meaningless
        return round(float((new / old) ** (1 / back) - 1) * 100, 2)

    rev, ni = revenue.get(fy), profit.get(fy)
    eq = equity.get(fy)
    capital = assets[fy] - current[fy] if fy in assets and fy in current else None
    return {
        "fiscal_year": fy.year,
        "net_income": ni,
        "roe_pct": ratio(ni, eq) if eq and eq > 0 else None,
        "roce_pct": ratio(ebit.get(fy), capital) if capital and capital > 0 else None,
        "revenue_growth_pct": growth(revenue, 1),
        "revenue_cagr_3y_pct": growth(revenue, 3),
        "profit_cagr_3y_pct": growth(profit, 3),
        "profit_margin_pct": ratio(ni, rev) if rev and rev > 0 else None,
        "debt_to_equity": ratio(debt.get(fy), eq, 1.0) if eq and eq > 0 else None,
    }


def price_on(prices: pd.Series, day: date) -> float | None:
    """Last close on or before `day`, if there was one within a week."""
    if prices is None or prices.empty:
        return None
    upto = prices[prices.index <= pd.Timestamp(day)].dropna()
    if upto.empty or upto.index[-1] < pd.Timestamp(day - PRICE_GAP):
        return None
    return float(upto.iloc[-1])


def forward_return(prices: pd.Series, start: date, days: int, last_day: date) -> float | None:
    """Total return % from `start` over `days`; None when that end date hasn't come yet."""
    end = start + timedelta(days=days)
    if end > last_day:
        return None
    a, b = price_on(prices, start), price_on(prices, end)
    return round((b / a - 1) * 100, 2) if a and b else None


def promoter_change(holdings: dict[date, float], as_of: date) -> float | None:
    """Change in promoter % between the two latest quarters disclosed by `as_of` (consecutive only)."""
    known = sorted((q for q in holdings if q <= as_of - HOLDING_LAG), reverse=True)
    if len(known) < 2 or (known[0] - known[1]).days > 100:
        return None
    return round(holdings[known[0]] - holdings[known[1]], 2)


def stock_as_of(
    current: Stock, income: pd.DataFrame, balance: pd.DataFrame, close: pd.Series, total: pd.Series,
    dividends: pd.Series, holdings: dict[date, float], as_of: date,
) -> Stock | None:
    """A detached Stock carrying only what was knowable on `as_of`; None without a price then."""
    price = price_on(close, as_of)
    if price is None:
        return None
    f = fundamentals_at(income, balance, as_of)
    shares = current.market_cap / current.price if current.market_cap and current.price else None
    profit, pe = f.get("net_income"), None
    if profit and shares:
        pe = round(price * shares / profit, 1) if profit > 0 else -1.0  # negative: loss-making
    year_ago = price_on(total, as_of - timedelta(days=365))
    now_total = price_on(total, as_of)
    paid = dividends[(dividends.index > pd.Timestamp(as_of - timedelta(days=365))) & (dividends.index <= pd.Timestamp(as_of))]
    return Stock(
        ticker=current.ticker, name=current.name, sector=current.sector, price=price,
        roe_pct=f.get("roe_pct"), roce_pct=f.get("roce_pct"),
        revenue_growth_pct=f.get("revenue_growth_pct"), revenue_cagr_3y_pct=f.get("revenue_cagr_3y_pct"),
        profit_cagr_3y_pct=f.get("profit_cagr_3y_pct"), profit_margin_pct=f.get("profit_margin_pct"),
        debt_to_equity=f.get("debt_to_equity"), pe_ratio=pe,
        return_1y_pct=round((now_total / year_ago - 1) * 100, 2) if year_ago and now_total else None,
        promoter_change_pp=promoter_change(holdings, as_of),
        dividend_yield_pct=round(float(paid.sum()) / price * 100, 2) if len(paid) else None,
    )


def summarize(replays: list[Replay]) -> str:
    """Markdown tables: per horizon, each verdict's average and median excess return and hit rate."""
    lines = []
    for horizon in HORIZONS:
        rows = [(r.verdict, ret, ex) for r in replays
                if (ret := r.returns.get(horizon)) is not None and (ex := r.excess.get(horizon)) is not None]
        if not rows:
            continue
        avg_all = statistics.mean(ret for _, ret, _ in rows)
        lines += [
            f"\n### {horizon} after each replay date ({len(rows)} calls; average stock {avg_all:+.1f}%)\n",
            "| Verdict | Calls | Avg return | Avg vs NIFTY 50 | Median vs NIFTY 50 | Beat NIFTY 50 | Avg vs average stock |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for verdict in ("Buy", "Hold", "Avoid", "Unrated"):
            got = [r for v, r, _ in rows if v == verdict]
            beat = [e for v, _, e in rows if v == verdict]
            if not got:
                continue
            lines.append(
                f"| {verdict} | {len(got)} | {statistics.mean(got):+.1f}% | {statistics.mean(beat):+.1f} pp "
                f"| {statistics.median(beat):+.1f} pp | {sum(e > 0 for e in beat) / len(beat):.0%} "
                f"| {statistics.mean(got) - avg_all:+.1f} pp |"
            )
    return "\n".join(lines)


def _cached(cache: Path, key: str, fetch: Callable[[], T]) -> T:
    path = cache / f"{key}.pkl"
    if path.exists():
        return cast(T, pickle.loads(path.read_bytes()))
    value = fetch()
    path.write_bytes(pickle.dumps(value))
    return value


def _statements(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Annual income and balance sheet; retried once, since Yahoo answers a throttle with empty tables."""
    for attempt in range(2):
        t = yf.Ticker(ticker)
        income, balance = t.income_stmt, t.balance_sheet
        if not (income.empty and balance.empty):
            return income, balance
        time.sleep(20 * (attempt + 1))
    return income, balance


def _replay_stock(
    current: Stock, frame: pd.DataFrame, bench: pd.Series, holdings: dict[date, float], cache: Path, last_day: date
) -> list[Replay]:
    """Every replay date's call on one stock, with the returns that followed."""
    fresh = not (cache / f"stmt-{current.ticker}.pkl").exists()
    income, balance = _cached(cache, f"stmt-{current.ticker}", partial(_statements, current.ticker))
    if fresh:
        time.sleep(1.0)  # pace Yahoo only on real fetches, not cache hits
    if frame["Close"].dropna().empty:
        return []  # Yahoo sent no prices (e.g. a recent listing or a renamed symbol)
    # The column is absent when no stock in the download paid a dividend on that day range
    paid = frame["Dividends"] if "Dividends" in frame.columns else pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    out = []
    for as_of in REPLAY_DATES:
        past = stock_as_of(current, income, balance, frame["Close"], frame["Adj Close"], paid[paid > 0], holdings, as_of)
        if past is None:
            continue
        call = data_call(past)
        returns = {h: forward_return(frame["Adj Close"], as_of, d, last_day) for h, d in HORIZONS.items()}
        index = {h: forward_return(bench, as_of, d, last_day) for h, d in HORIZONS.items()}
        excess = {h: round(r - b, 2) if (r := returns[h]) is not None and (b := index[h]) is not None else None
                  for h in HORIZONS}
        out.append(Replay(current.ticker, as_of, call.verdict, call.score, returns, excess))
    return out


async def run(limit: int | None, cache: Path, csv: Path | None) -> str:
    from app.core.database import AsyncSessionLocal
    from app.services.nse_market import index_members

    cache.mkdir(parents=True, exist_ok=True)
    members = await index_members("NIFTY 500") or []
    tickers = [m["ticker"] for m in members][:limit]
    async with AsyncSessionLocal() as db:
        stocks = {s.ticker: s for s in (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))).scalars()}
        rows = (await db.execute(select(Shareholding).where(Shareholding.ticker.in_(tickers)))).scalars().all()
        for s in stocks.values():
            db.expunge(s)
    holdings: dict[str, dict[date, float]] = {}
    for h in rows:
        holdings.setdefault(h.ticker, {})[h.quarter] = h.promoter_pct

    start = REPLAY_DATES[0] - timedelta(days=400)
    raw = _cached(cache, f"prices-{len(tickers)}-{start}", lambda: yf.download(
        [*tickers, BENCHMARK], start=start.isoformat(), auto_adjust=False, actions=True,
        group_by="ticker", progress=False, threads=True,
    ))
    assert isinstance(raw, pd.DataFrame)
    last_day = raw.index.max().date()
    bench = raw[BENCHMARK]["Adj Close"]

    replays: list[Replay] = []
    skipped: list[str] = []
    for i, ticker in enumerate(tickers):
        current = stocks.get(ticker)
        if current is None or ticker not in raw.columns.get_level_values(0):
            continue
        try:
            replays += _replay_stock(current, raw[ticker], bench, holdings.get(ticker, {}), cache, last_day)
        except Exception as e:  # one stock's odd data shouldn't end a 500-stock run
            skipped.append(ticker)
            print(f"skipped {ticker}: {type(e).__name__}: {e}", flush=True)
        if i % 50 == 49:
            print(f"... {i + 1}/{len(tickers)} stocks", flush=True)

    if csv:
        pd.DataFrame([
            {"ticker": r.ticker, "as_of": r.as_of, "verdict": r.verdict, "score": r.score,
             **{f"ret_{h}": r.returns[h] for h in HORIZONS}, **{f"excess_{h}": r.excess[h] for h in HORIZONS}}
            for r in replays
        ]).to_csv(csv, index=False)
    counts = pd.Series([r.verdict for r in replays]).value_counts().to_dict()
    header = (
        f"## Verdict backtest: {len(stocks)} Nifty 500 stocks, replay dates "
        f"{', '.join(d.isoformat() for d in REPLAY_DATES)}; prices to {last_day}\n\n"
        f"Calls made: {counts}" + (f"\n\nSkipped on bad data: {', '.join(skipped)}" if skipped else "")
    )
    return header + "\n" + summarize(replays)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="first N Nifty 500 stocks only")
    parser.add_argument("--cache", type=Path, default=Path(".backtest-cache"))
    parser.add_argument("--csv", type=Path, default=None, help="write every call and its returns here")
    args = parser.parse_args()
    print(asyncio.run(run(args.limit, args.cache, args.csv)))
