"""Tests for the watchlist API and logout token revocation."""

import pytest
from httpx import AsyncClient

from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import stock_lookup


async def _headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def yahoo(monkeypatch):
    """Offline Yahoo: only ZZZZ has a quote."""
    calls: list[str] = []

    def _close(ticker):
        calls.append(ticker)
        return 12.5 if ticker == "ZZZZ" else None

    monkeypatch.setattr(stock_lookup, "last_close", _close)
    return calls


@pytest.mark.asyncio
async def test_add_list_and_remove(client: AsyncClient, db_session, yahoo):
    db_session.add(Stock(ticker="AAPL", name="Apple Inc.", price=189.42))
    await db_session.commit()
    headers = await _headers(client)

    resp = await client.post("/api/v1/watchlist/", json={"ticker": "aapl"}, headers=headers)
    assert resp.status_code == 201
    assert [i["ticker"] for i in resp.json()["items"]] == ["AAPL"]
    assert yahoo == []  # already tracked, no lookup

    # Adding twice is a no-op
    resp = await client.post("/api/v1/watchlist/", json={"ticker": "AAPL"}, headers=headers)
    assert len(resp.json()["items"]) == 1

    listed = await client.get("/api/v1/watchlist/", headers=headers)
    assert listed.json()["items"][0]["price"] == "$189.42"

    assert (await client.delete("/api/v1/watchlist/AAPL", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/watchlist/", headers=headers)).json()["items"] == []
    assert (await client.delete("/api/v1/watchlist/AAPL", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_unknown_ticker_is_verified_before_tracking(client: AsyncClient, yahoo):
    headers = await _headers(client)

    bad = await client.post("/api/v1/watchlist/", json={"ticker": "NOPE"}, headers=headers)
    assert bad.status_code == 404

    good = await client.post("/api/v1/watchlist/", json={"ticker": "ZZZZ"}, headers=headers)
    assert good.status_code == 201
    assert good.json()["items"][0]["price"] == "$12.50"

    invalid = await client.post(
        "/api/v1/watchlist/", json={"ticker": "DROP TABLE"}, headers=headers
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_watchlists_are_per_user(client: AsyncClient, db_session, yahoo):
    db_session.add(Stock(ticker="AAPL", name="Apple Inc."))
    await db_session.commit()
    await client.post("/api/v1/watchlist/", json={"ticker": "AAPL"}, headers=await _headers(client))

    other = {"email": "other@quantara.com", "password": "securepassword123"}
    token = (await client.post("/api/v1/auth/register", json=other)).json()["access_token"]
    resp = await client.get("/api/v1/watchlist/", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_logout_revokes_access_and_refresh_tokens(client: AsyncClient):
    headers = await _headers(client)  # also stores the refresh cookie on the client
    refresh_value = client.cookies.get("quantara_refresh")

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert "quantara_refresh=" in logout.headers["set-cookie"]  # cleared

    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    # Replaying the old refresh cookie no longer works
    client.cookies.set("quantara_refresh", refresh_value, domain="test", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    # Logging in again issues working tokens
    assert (await client.get("/api/v1/users/me", headers=await _headers(client))).status_code == 200


@pytest.mark.asyncio
async def test_portfolio_rejects_unknown_and_duplicate_tickers(client: AsyncClient, yahoo):
    headers = await _headers(client)
    bad = await client.post(
        "/api/v1/portfolio/",
        json={"name": "Typo", "positions": [{"ticker": "NOPE", "weight": 1.0}]},
        headers=headers,
    )
    assert bad.status_code == 422
    assert "NOPE" in bad.json()["detail"]

    dup = await client.post(
        "/api/v1/portfolio/",
        json={"name": "Dup", "positions": [{"ticker": "ZZZZ", "weight": 0.5}, {"ticker": "zzzz", "weight": 0.5}]},
        headers=headers,
    )
    assert dup.status_code == 422
    # Nothing was written for the rejected requests
    assert (await client.get("/api/v1/portfolio/", headers=headers)).json()["portfolios"] == []


@pytest.mark.asyncio
async def test_watchlist_alerts_unread_then_seen(client: AsyncClient, db_session, yahoo):

    from app.models.signal import Signal

    db_session.add_all([Stock(ticker="AAPL", name="Apple Inc."), Stock(ticker="MSFT", name="Microsoft")])
    await db_session.commit()
    headers = await _headers(client)
    await client.post("/api/v1/watchlist/", json={"ticker": "AAPL"}, headers=headers)

    now = utcnow()
    db_session.add_all([
        Signal(ticker="AAPL", signal_type="insider_buying", strength=70, confidence=0.8, timestamp=now),
        Signal(ticker="MSFT", signal_type="insider_buying", strength=70, confidence=0.8, timestamp=now),
    ])
    await db_session.commit()

    alerts = (await client.get("/api/v1/watchlist/alerts", headers=headers)).json()
    assert [a["ticker"] for a in alerts["alerts"]] == ["AAPL"]  # unwatched MSFT excluded
    assert alerts["unread_count"] == 1

    assert (await client.post("/api/v1/watchlist/alerts/seen", headers=headers)).status_code == 204
    alerts = (await client.get("/api/v1/watchlist/alerts", headers=headers)).json()
    assert alerts["unread_count"] == 0
    assert alerts["alerts"][0]["unread"] is False
