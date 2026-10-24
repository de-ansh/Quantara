"""Tests for personal data export and account deletion."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.price_alert import PriceAlert
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import WatchlistItem


async def _setup(client: AsyncClient, db_session) -> dict:
    db_session.add(Stock(ticker="AAPL", name="Apple", price=200.0))
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    await client.put("/api/v1/users/credentials", headers=headers,
                     json={"openai_api_key": "sk-proj-secret-value-123456789"})
    await client.post("/api/v1/watchlist/", headers=headers, json={"ticker": "AAPL"})
    await client.post("/api/v1/alerts/price/", headers=headers,
                      json={"ticker": "AAPL", "direction": "above", "target_price": 250})
    await client.post("/api/v1/portfolio/", headers=headers,
                      json={"name": "Mine", "positions": [{"ticker": "AAPL", "weight": 1, "shares": 3}]})
    return headers


@pytest.mark.asyncio
async def test_export_contains_my_data_but_no_secrets(client: AsyncClient, db_session):
    headers = await _setup(client, db_session)
    resp = await client.get("/api/v1/users/me/export", headers=headers)

    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["profile"]["email"] == "test@quantara.com"
    assert data["profile"]["has_openai_key"] is True
    assert data["portfolios"][0]["positions"][0] == {
        "ticker": "AAPL", "weight": 1.0, "shares": 3.0, "cost_basis": 0.0
    }
    assert data["watchlist"][0]["ticker"] == "AAPL"
    assert data["price_alerts"][0]["target_price"] == 250
    assert any(entry["action"] == "login" for entry in data["activity_log"])
    raw = resp.text
    assert "sk-proj-secret" not in raw and "hashed_password" not in raw and "$2b$" not in raw


@pytest.mark.asyncio
async def test_delete_account_removes_everything(client: AsyncClient, db_session):
    headers = await _setup(client, db_session)

    wrong = await client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": "nope"})
    assert wrong.status_code == 400

    resp = await client.request("DELETE", "/api/v1/users/me", headers=headers, json={"password": "password"})
    assert resp.status_code == 204
    assert "quantara_refresh=" in resp.headers.get("set-cookie", "")

    for model in (User, Portfolio, PortfolioPosition, WatchlistItem, PriceAlert):
        assert (await db_session.execute(select(func.count()).select_from(model))).scalar_one() == 0
    user_logs = (await db_session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.user_id.is_not(None))
    )).scalar_one()
    assert user_logs == 0
    erasure = (await db_session.execute(select(AuditLog).where(AuditLog.action == "delete_account"))).scalar_one()
    assert erasure.user_id is None

    # The stock data itself is shared and stays
    assert (await db_session.execute(select(Stock))).scalar_one().ticker == "AAPL"
    # The old token is useless and login is gone
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    relogin = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    assert relogin.status_code == 401
