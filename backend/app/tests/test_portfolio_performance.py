"""Tests for holdings valuation / P&L and share-derived weights."""

from datetime import datetime

import pytest
from httpx import AsyncClient

from app.models.stock import Stock
from app.services import price_service, stock_lookup


async def _headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def market(monkeypatch):
    """Offline prices; records which tickers the stale-price refresh asked for."""
    refreshed: list[list[str]] = []

    def _quotes(tickers):
        refreshed.append(sorted(tickers))
        return {"MSFT": (420.0, 400.0)}

    monkeypatch.setattr(price_service, "fetch_quotes", _quotes)
    monkeypatch.setattr(stock_lookup, "last_close", lambda t: None)
    return refreshed


@pytest.mark.asyncio
async def test_performance_values_holdings_per_currency(client: AsyncClient, db_session, market):
    now = datetime.utcnow()
    db_session.add_all([
        Stock(ticker="AAPL", name="Apple", sector="Technology", price=200.0,
              previous_close=190.0, price_updated_at=now),
        Stock(ticker="MSFT", name="Microsoft", sector="Technology", price=300.0),  # stale
        Stock(ticker="TCS.NS", name="TCS", sector="IT", price=4000.0,
              previous_close=4100.0, price_updated_at=now),
        Stock(ticker="GLD", name="Gold", price=180.0, price_updated_at=now),
    ])
    await db_session.commit()
    headers = await _headers(client)

    created = await client.post("/api/v1/portfolio/", headers=headers, json={
        "name": "Mixed",
        "positions": [
            {"ticker": "AAPL", "weight": 0.4, "shares": 10, "cost_basis": 150},
            {"ticker": "MSFT", "weight": 0.3, "shares": 5, "cost_basis": 0},     # no cost given
            {"ticker": "TCS.NS", "weight": 0.2, "shares": 2, "cost_basis": 3500},
            {"ticker": "GLD", "weight": 0.1},                                   # weight-only
        ],
    })
    assert created.status_code == 201
    perf = (await client.get(f"/api/v1/portfolio/{created.json()['id']}/performance", headers=headers)).json()

    assert market == [["MSFT"]]  # only the stale quote was refreshed
    by = {h["ticker"]: h for h in perf["holdings"]}
    assert perf["weight_only_tickers"] == ["GLD"]

    assert by["AAPL"]["market_value"] == 2000.0
    assert by["AAPL"]["unrealized_pnl"] == 500.0
    assert by["AAPL"]["unrealized_pnl_pct"] == pytest.approx(33.33, abs=0.01)
    assert by["AAPL"]["day_change"] == 100.0
    assert by["MSFT"]["price"] == 420.0 and by["MSFT"]["unrealized_pnl"] is None

    totals = {t["currency"]: t for t in perf["totals"]}
    assert set(totals) == {"USD", "INR"}  # never summed across currencies
    assert totals["USD"]["market_value"] == 2000.0 + 2100.0
    assert totals["USD"]["unrealized_pnl"] == 500.0  # only positions with a cost basis
    assert totals["USD"]["cost_value"] == 1500.0
    assert totals["USD"]["sector_allocation"] == {"Technology": 100.0}
    assert totals["INR"]["unrealized_pnl"] == 1000.0 and totals["INR"]["day_change"] == -200.0


@pytest.mark.asyncio
async def test_weights_derived_from_shares(client: AsyncClient, db_session, market):
    db_session.add_all([
        Stock(ticker="AAPL", name="Apple", price=200.0),
        Stock(ticker="MSFT", name="Microsoft", price=400.0),
        Stock(ticker="TCS.NS", name="TCS", price=4000.0),
    ])
    await db_session.commit()
    headers = await _headers(client)

    resp = await client.post("/api/v1/portfolio/", headers=headers, json={
        "name": "By shares",
        "positions": [{"ticker": "AAPL", "shares": 3}, {"ticker": "MSFT", "shares": 1}],
    })
    weights = {p["ticker"]: p["weight"] for p in resp.json()["positions"]}
    assert weights == {"AAPL": pytest.approx(0.6), "MSFT": pytest.approx(0.4)}

    mixed = await client.post("/api/v1/portfolio/", headers=headers, json={
        "name": "Mixed", "positions": [{"ticker": "AAPL", "shares": 1}, {"ticker": "TCS.NS", "shares": 1}],
    })
    assert mixed.status_code == 422

    neither = await client.post("/api/v1/portfolio/", headers=headers, json={
        "name": "Empty", "positions": [{"ticker": "AAPL"}],
    })
    assert neither.status_code == 422
