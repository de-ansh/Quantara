"""NSE large-deal and promoter-pledge signals."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.listed_security import ListedSecurity
from app.models.signal import Signal as DBSignal
from app.models.stock import Stock
from app.services import india_signals
from app.services.india_signals import deal_signal, parse_deals, parse_pledges, pledge_signal
from app.services.recommendation_engine import signal_score

BULK = """Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price,Remarks
09-NOV-2026,ACME,Acme Ltd.,FUND A,BUY,"1,000,000",100.00,-
09-NOV-2026,ACME,Acme Ltd.,FUND B,SELL,200000,101.00,-
09-NOV-2026,FLAT,Flat Ltd.,FUND C,BUY,500000,10.00,-
09-NOV-2026,FLAT,Flat Ltd.,FUND D,SELL,500000,10.00,-
"""
BLOCK = """Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price
09-NOV-2026,DUMP,Dump Ltd,PROMOTER TRUST,SELL,3000000,430.00
"""
PLEDGES = {"data": [
    {"comName": "Acme Limited", "percPromoterShares": "     45.00", "percPromoterHolding": " 60.00", "shp": "30-Sep-2026"},
    {"comName": "Clean Ltd", "percPromoterShares": "0.00", "percPromoterHolding": "51.00", "shp": "30-Sep-2026"},
]}


def test_deals_net_per_stock_and_carry_direction():
    deals = parse_deals(BULK, BLOCK)
    assert deals["ACME"]["buy_qty"] == 1_000_000 and deals["ACME"]["sell_qty"] == 200_000

    bought = deal_signal("ACME.NS", deals["ACME"], shares_outstanding=40_000_000)  # net 2% of the company
    assert bought.strength == 80.0 and bought.metadata["direction"] == "bullish"
    sold = deal_signal("DUMP.NS", deals["DUMP"], shares_outstanding=60_000_000)  # net -5%
    assert sold.strength == 100.0 and sold.metadata["direction"] == "bearish"
    assert deal_signal("FLAT.NS", deals["FLAT"], shares_outstanding=10_000_000) is None  # buys and sells offset

    assert signal_score([(bought.strength, bought.metadata)]) == 90.0
    assert signal_score([(sold.strength, sold.metadata)]) == 0.0


def test_only_a_high_promoter_pledge_is_a_signal():
    pledges = parse_pledges(PLEDGES)
    acme = pledge_signal("ACME.NS", pledges["acme"])
    assert acme.strength == 67.5 and acme.metadata["direction"] == "bearish"
    assert pledge_signal("CLEAN.NS", pledges["clean"]) is None


@pytest.mark.asyncio
async def test_run_stores_signals_for_tracked_nse_stocks_once(db_session, monkeypatch):
    db_session.add_all([
        Stock(ticker="ACME.NS", name="Acme", price=100.0, market_cap=4e9),  # 40M shares
        Stock(ticker="AAPL", name="Apple"),  # not an NSE stock: ignored
        ListedSecurity(ticker="ACME.NS", name="Acme Limited", exchange="NSE"),
    ])
    await db_session.commit()
    pages = {india_signals.BULK_DEALS: BULK, india_signals.BLOCK_DEALS: BLOCK, india_signals.PLEDGES: json.dumps(PLEDGES)}

    async def fake_fetch(client, url):
        return SimpleNamespace(text=pages[url], json=lambda: json.loads(pages[url]))

    monkeypatch.setattr(india_signals, "_fetch", fake_fetch)
    assert await india_signals.run_india_signals(db_session) == 2
    await india_signals.run_india_signals(db_session)  # the hourly pass sees the same day's file again
    stored = (await db_session.execute(select(DBSignal.signal_type))).scalars().all()
    assert sorted(stored) == ["large_deal", "promoter_pledge"]
