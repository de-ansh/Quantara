"""ROCE and 3-year growth from statements; promoter holding changes from NSE."""

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.models.shareholding import Shareholding
from app.models.signal import Signal as DBSignal
from app.models.stock import Stock
from app.services import shareholding
from app.services.statements import statement_metrics

YEARS = pd.to_datetime(["2026-03-31", "2025-03-31", "2024-03-31", "2023-03-31"])


def _frame(rows: dict[str, list[float | None]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=YEARS).T  # Yahoo layout: rows are line items, columns are years


def test_roce_and_three_year_growth():
    income = _frame({"EBIT": [300, 250, 200, 150], "Total Revenue": [1331, 1210, 1100, 1000],
                     "Net Income": [200, 150, -50, 100]})
    balance = _frame({"Total Assets": [2000, 1800, 1600, 1500], "Current Liabilities": [500, 400, 400, 300]})
    m = statement_metrics(income, balance)
    assert m["roce_pct"] == 20.0  # 300 / (2000 - 500)
    assert m["revenue_cagr_3y_pct"] == 10.0  # 1000 -> 1331 over three years
    assert m["profit_cagr_3y_pct"] == 25.99  # 100 -> 200; the loss year in between doesn't matter

    # A lender has no EBIT or current liabilities; a loss at either end makes growth meaningless
    bank = statement_metrics(_frame({"Total Revenue": [100, 90, 80, 70], "Net Income": [10, 8, 6, -5]}),
                             _frame({"Total Assets": [5000, 4000, 3000, 2000]}))
    assert bank["roce_pct"] is None and bank["profit_cagr_3y_pct"] is None
    assert bank["revenue_cagr_3y_pct"] == 12.62
    assert statement_metrics(pd.DataFrame(), pd.DataFrame()) == {
        "roce_pct": None, "revenue_cagr_3y_pct": None, "profit_cagr_3y_pct": None}


def _nse(symbol: str, day: str, pct: str) -> dict:
    return {"symbol": symbol, "date": day, "pr_and_prgrp": pct}


@pytest.mark.asyncio
async def test_promoter_change_is_stored_and_signalled(db_session, monkeypatch):
    db_session.add_all([Stock(ticker="UP.NS", name="Up"), Stock(ticker="FLAT.NS", name="Flat"),
                        Stock(ticker="AAPL", name="Apple")])
    await db_session.commit()
    calls = []

    async def fake_get_json(client, url):
        calls.append(url)
        if url == shareholding.MASTER:  # latest quarter only, for every company
            return [_nse("UP", "30-SEP-2026", "52.50"), _nse("FLAT", "30-SEP-2026", "40.00"),
                    _nse("OTHER", "30-SEP-2026", "70"), {"symbol": "BAD", "date": "x", "pr_and_prgrp": "-"}]
        if url.endswith("symbol=UP"):
            # A revised Sep filing listed before the original
            return [_nse("UP", "30-SEP-2026", "52.50"), _nse("UP", "30-SEP-2026", "51.00"), _nse("UP", "30-JUN-2026", "50.00")]
        if url.endswith("symbol=FLAT"):
            return [_nse("FLAT", "30-SEP-2026", "40.00"), _nse("FLAT", "30-JUN-2026", "40.20")]
        return None

    monkeypatch.setattr(shareholding, "_get_json", fake_get_json)
    monkeypatch.setattr(shareholding.asyncio, "sleep", lambda s: _noop())

    assert await shareholding.refresh_shareholding(db_session) == 1  # only UP moved a point or more
    up = await db_session.get(Stock, "UP.NS")
    await db_session.refresh(up)
    assert (up.promoter_pct, up.promoter_change_pp, up.shareholding_quarter) == (52.5, 2.5, date(2026, 9, 30))
    signal = (await db_session.execute(select(DBSignal))).scalar_one()
    assert signal.ticker == "UP.NS" and signal.data["direction"] == "bullish" and signal.strength == 50.0
    stored = (await db_session.execute(select(Shareholding.ticker))).scalars().all()
    assert "OTHER.NS" not in stored  # untracked companies aren't kept

    # Next run: both have two quarters, so no per-company history calls are needed
    calls.clear()
    await shareholding.refresh_shareholding(db_session)
    assert calls == [shareholding.MASTER]


async def _noop():
    return None


@pytest.mark.asyncio
async def test_empty_statements_are_retried_tomorrow_not_next_week(db_session, monkeypatch):
    from datetime import timedelta

    from app.core.clock import utcnow
    from app.services import statements

    db_session.add_all([Stock(ticker="OK.NS"), Stock(ticker="THROTTLED.NS")])
    await db_session.commit()
    metrics = {"roce_pct": 20.0, "revenue_cagr_3y_pct": 10.0, "profit_cagr_3y_pct": None}
    monkeypatch.setattr(statements, "fetch_statement_metrics", lambda t: metrics if t == "OK.NS" else None)
    monkeypatch.setattr(statements, "PAUSE_SECONDS", 0)

    assert await statements.refresh_statements(db_session) == 1
    ok, throttled = await db_session.get(Stock, "OK.NS"), await db_session.get(Stock, "THROTTLED.NS")
    assert ok.roce_pct == 20.0 and throttled.roce_pct is None
    due_again = throttled.statements_updated_at + statements.STATEMENTS_MAX_AGE
    assert abs((due_again - utcnow()) - timedelta(days=1)) < timedelta(minutes=1)
    assert await statements.refresh_statements(db_session) == 0  # nothing due yet: no hammering every pass
