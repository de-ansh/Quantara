"""Daily technical snapshot: RSI, moving-average gaps, 52-week position, turnover; screener filters; most traded."""

import pytest

from app.api.v1.market import most_traded
from app.core.clock import utcnow
from app.models.stock import Stock
from app.services.price_service import fetch_year_history, refresh_technicals
from app.services.technicals import screener_snapshot


def test_snapshot_on_a_known_series():
    closes = [100.0] * 199 + [80.0] + [100.0 + i for i in range(1, 51)]  # dips to 80, then climbs to 150
    volumes = [1_000.0] * len(closes)
    snap = screener_snapshot(closes, volumes)
    assert snap is not None
    assert snap["from_high_52w_pct"] == 0.0  # closing at the high
    assert snap["from_low_52w_pct"] == 87.5  # 150 vs the 80 low
    assert snap["rsi_14"] > 90  # 50 straight rises; Wilder smoothing keeps a trace of the earlier dip
    assert snap["sma50_gap_pct"] == round((150 / (sum(range(101, 151)) / 50) - 1) * 100, 2)
    assert snap["turnover_1d"] == 150_000.0
    assert snap["turnover_20d"] == sum(c * 1_000 for c in closes[-20:]) / 20


def test_too_little_history_gives_nothing():
    assert screener_snapshot([100.0] * 10, [1.0] * 10) is None


def test_year_history_reads_the_batched_download():
    history = fetch_year_history(["AAA.NS", "BBB.NS"])
    assert set(history) == {"AAA.NS", "BBB.NS"}
    closes, volumes = history["AAA.NS"]
    assert len(closes) == len(volumes) > 200 and volumes[0] == 1_000_000.0


@pytest.mark.asyncio
async def test_refresh_fills_stale_stocks_once_a_day(db_session):
    db_session.add_all([Stock(ticker="AAA.NS", name="A", price=100), Stock(ticker="NOPRICE.NS", name="N")])
    await db_session.commit()
    assert await refresh_technicals(db_session) == 1  # stocks without a price are skipped
    stock = await db_session.get(Stock, "AAA.NS")
    assert stock.rsi_14 is not None and stock.turnover_20d and stock.technicals_updated_at is not None
    assert await refresh_technicals(db_session) == 0  # fresh until tomorrow


@pytest.mark.asyncio
async def test_screener_filters_and_sorts_on_technicals(client, db_session):
    now = utcnow()
    db_session.add_all([
        Stock(ticker="HOT.NS", name="Hot", price=100, rsi_14=78, sma200_gap_pct=25, from_high_52w_pct=-1, turnover_1d=9e9, turnover_20d=8e9, price_updated_at=now),
        Stock(ticker="COLD.NS", name="Cold", price=100, rsi_14=25, sma200_gap_pct=-12, from_high_52w_pct=-40, turnover_1d=5e8, turnover_20d=4e8, price_updated_at=now),
        Stock(ticker="FLAT.NS", name="Flat", price=100, rsi_14=50, sma200_gap_pct=2, from_high_52w_pct=-10, turnover_1d=1e9, turnover_20d=2e9, price_updated_at=now),
    ])
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    async def tickers(**params):
        resp = await client.get("/api/v1/stocks/search", params=params, headers=headers)
        assert resp.status_code == 200, resp.text
        return [s["ticker"] for s in resp.json()["stocks"]]

    assert await tickers(rsi_max=30) == ["COLD.NS"]
    assert await tickers(sma200_gap_min=0, sort="-rsi") == ["HOT.NS", "FLAT.NS"]
    assert await tickers(from_high_min=-5) == ["HOT.NS"]
    assert await tickers(turnover_min_cr=100, sort="-turnover") == ["HOT.NS", "FLAT.NS"]  # ₹100 Cr = 1e9


def test_most_traded_ranks_by_last_session():
    now = utcnow()
    stocks = [
        Stock(ticker=f"S{i}.NS", name=f"S{i}", price=100, previous_close=99, turnover_1d=i * 1e8, price_updated_at=now)
        for i in range(1, 13)
    ] + [Stock(ticker="NONE.NS", name="N", price=100, price_updated_at=now)]
    top = most_traded(stocks)
    assert [m.ticker for m in top][:2] == ["S12.NS", "S11.NS"] and len(top) == 10
    assert top[0].turnover == 12e8 and top[0].change_pct == 1.01
