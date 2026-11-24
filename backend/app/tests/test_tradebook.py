"""Tradebook stored with a portfolio: buy dates for tax-aware rebalancing, gaps against holdings, and XIRR."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.api.v1 import tax
from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import price_service, stock_lookup
from app.services.portfolio_balance import Target, rebalance_plan
from app.services.tax_harvest import Lot, sale_from, xirr

TODAY = date(2030, 6, 1)


def test_sale_splits_gains_first_in_first_out_and_spots_a_lot_about_to_turn_long_term():
    lots = [Lot("X", date(2028, 1, 1), 10, 100), Lot("X", date(2029, 6, 10), 10, 150)]  # long-term, turns 11 Jun 2030
    sale = sale_from(lots, 15, 200, TODAY)
    assert (sale.long_term, sale.short_term) == (1000, 250)  # 10 x (200-100), then 5 x (200-150)
    assert sale.wait_until == date(2030, 6, 11)
    assert sale_from(lots, 5, 200, TODAY).wait_until is None  # only the old lot is touched


def test_xirr_matches_a_simple_annual_return_and_refuses_what_it_cannot_answer():
    assert xirr([(date(2029, 1, 1), -1000), (date(2030, 1, 1), 1100)]) == pytest.approx(10.0, abs=0.01)
    assert xirr([(date(2029, 1, 1), -1000), (date(2029, 1, 10), 1100)]) is None  # under a month
    assert xirr([(date(2029, 1, 1), 1000), (date(2030, 1, 1), 1100)]) is None  # no money in


def h(ticker, value, pnl, price=10.0):
    return SimpleNamespace(kind="stock", ticker=ticker, name=ticker, sector=ticker, currency="INR",
                           market_value=value, unrealized_pnl=pnl, price=price, shares=value / price)


def test_with_buy_dates_a_long_term_gain_is_sold_before_a_short_term_one():
    holdings = [h("SHORT", 500, 100), h("LONG", 500, 100), h("DEBT", 0.01, 0)]
    lots = {"SHORT": [Lot("SHORT", TODAY - timedelta(days=100), 50, 8)],
            "LONG": [Lot("LONG", TODAY - timedelta(days=800), 50, 8)]}
    target = Target(70, 30, 0, 0, max_stock=100)
    [sell, _] = rebalance_plan(holdings, target, {}, lots=lots, today=TODAY)
    assert (sell.ticker, sell.reason, sell.long_term_gain, sell.short_term_gain) == ("LONG", "long-term gain, taxed at 12.5%", 60, 0)
    # Without buy dates the two look the same and nothing is split
    [blind, _] = rebalance_plan(holdings, target, {}, today=TODAY)
    assert blind.short_term_gain is None and blind.reason == "smallest gain in this class"


def test_lots_that_do_not_cover_the_holding_are_not_trusted():
    holdings = [h("PART", 1000, 200), h("DEBT", 0.01, 0)]
    lots = {"PART": [Lot("PART", TODAY - timedelta(days=800), 40, 8)]}  # 40 of 100 shares
    [sell, _] = rebalance_plan(holdings, Target(50, 50, 0, 0, max_stock=100), {}, lots=lots, today=TODAY)
    assert sell.short_term_gain is None


@pytest.mark.asyncio
async def test_tradebook_import_summary_tax_and_delete(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(tax, "_split_dates", lambda t: [])  # no network
    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {})
    monkeypatch.setattr(stock_lookup, "last_close", lambda t: None)
    now = utcnow()
    db_session.add_all([
        Stock(ticker="AAA.NS", name="Example A", sector="Banks", price=150.0, price_updated_at=now),
        Stock(ticker="BBB.NS", name="Example B", sector="Energy", price=100.0, price_updated_at=now),
    ])
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = await client.post("/api/v1/portfolio/", headers=headers, json={"name": "Broker", "positions": [
        {"ticker": "AAA.NS", "weight": 0.5, "shares": 10, "cost_basis": 100},
        {"ticker": "BBB.NS", "weight": 0.5, "shares": 5, "cost_basis": 100},
    ]})
    pid = created.json()["id"]
    assert (await client.get(f"/api/v1/portfolio/{pid}/trades", headers=headers)).json() is None

    two_years_ago = (date.today() - timedelta(days=730)).isoformat()
    trades = [
        {"symbol": "AAA.NS", "date": two_years_ago, "side": "buy", "quantity": 12, "price": 100},
        {"symbol": "AAA.NS", "date": (date.today() - timedelta(days=400)).isoformat(), "side": "sell", "quantity": 2, "price": 120},
        {"symbol": "BBB.NS", "date": two_years_ago, "side": "buy", "quantity": 2, "price": 100},  # 3 shares unexplained
    ]
    summary = (await client.put(f"/api/v1/portfolio/{pid}/trades", headers=headers, json={"trades": trades})).json()
    assert summary["trades"] == 3 and summary["first_trade"] == two_years_ago and summary["excluded"] == []
    assert summary["gaps"] == [{"ticker": "BBB.NS", "portfolio_shares": 5.0, "tradebook_shares": 2.0}]
    assert summary["xirr"] is not None and summary["xirr"] > 0

    await client.put("/api/v1/portfolio/target-mix", headers=headers,
                     json={"equity": 50, "debt": 50, "cash": 0, "gold": 0, "max_stock": 100, "max_sector": 100})
    balance = (await client.get(f"/api/v1/portfolio/{pid}/balance", headers=headers)).json()
    sells = [t for t in balance["plan"] if t["action"] == "sell"]
    aaa = next(t for t in sells if t["ticker"] == "AAA.NS")
    assert aaa["long_term_gain"] > 0 and aaa["short_term_gain"] == 0
    assert balance["exemption_left"] == 125000.0
    # BBB's lots don't cover its 5 shares, so the plan's total tax can't be known if BBB is sold
    assert (balance["plan_tax"] is None) == any(t["ticker"] == "BBB.NS" for t in sells)

    other = await client.put("/api/v1/portfolio/999999/trades", headers=headers, json={"trades": trades})
    assert other.status_code == 404
    assert (await client.delete(f"/api/v1/portfolio/{pid}/trades", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/portfolio/{pid}/trades", headers=headers)).json() is None
