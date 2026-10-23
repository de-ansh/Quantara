import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_market_status_endpoint(client: AsyncClient):
    """Test the new market status feed endpoint."""
    # Authenticate first
    reg_payload = {"email": "market_user@quantara.com", "password": "securepassword123"}
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201

    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch market status
    resp = await client.get("/api/v1/market/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "vix" in data
    assert "alerts" in data

    # Assert VIX properties
    vix = data["vix"]
    assert "value" in vix
    assert "change" in vix
    assert "change_percent" in vix
    assert vix["status"] in ["low", "moderate", "high"]

    # Assert macroeconomic alerts
    alerts = data["alerts"]
    assert len(alerts) > 0
    assert "time" in alerts[0]
    assert "type" in alerts[0]
    assert "text" in alerts[0]


@pytest.mark.asyncio
async def test_users_risk_profile_sync(client: AsyncClient):
    """Test user profile retrieval and updating risk tolerance parameters."""
    reg_payload = {"email": "profile_user@quantara.com", "password": "securepassword123"}
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get initial profile
    get_resp = await client.get("/api/v1/users/me", headers=headers)
    assert get_resp.status_code == 200
    profile = get_resp.json()
    assert profile["email"] == "profile_user@quantara.com"

    # 2. Update risk profile
    update_payload = {
        "risk_level": "Aggressive",
        "volatility_tolerance": 82.5,
        "investment_horizon": 36,
        "sector_preferences": {"Technology": 50.0, "Healthcare": 20.0},
    }
    post_resp = await client.post(
        "/api/v1/users/risk-profile", json=update_payload, headers=headers
    )
    assert post_resp.status_code == 200
    updated_profile = post_resp.json()
    assert updated_profile["risk_level"] == "Aggressive"
    assert updated_profile["volatility_tolerance"] == 82.5
    assert updated_profile["investment_horizon"] == 36
    assert updated_profile["sector_preferences"]["Technology"] == 50.0

    # 3. Retrieve profile again and verify DB persistence
    get_resp2 = await client.get("/api/v1/users/me", headers=headers)
    assert get_resp2.status_code == 200
    db_profile = get_resp2.json()
    assert db_profile["risk_level"] == "Aggressive"
    assert db_profile["volatility_tolerance"] == 82.5
    assert db_profile["investment_horizon"] == 36


@pytest.mark.asyncio
async def test_stored_credentials_reach_risk_endpoint(client: AsyncClient):
    """Server-stored credentials (not request headers) are used by analysis endpoints."""
    reg_payload = {"email": "headers_user@quantara.com", "password": "securepassword123"}
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    put_resp = await client.put(
        "/api/v1/users/credentials",
        json={
            "openai_api_key": "sk-proj-testkeyoverride12345",
            "sec_user_agent": "TestAgent Override contact@test.com",
        },
        headers=headers,
    )
    assert put_resp.status_code == 200

    resp = await client.get("/api/v1/stocks/AAPL/risk", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_market_status_falls_back_when_yahoo_unreachable(monkeypatch):
    """A Yahoo outage yields last-known levels, and alerts reflect the quotes."""
    from app.api.v1 import market

    def _boom(symbol):
        raise ConnectionError("offline")

    monkeypatch.setattr(market.yf, "Ticker", _boom)
    monkeypatch.setattr(market, "_quote_cache", {"at": 0.0, "quotes": None})

    status = await market.get_market_status()
    assert status.vix.value == market._FALLBACK_QUOTES["^VIX"][0]
    assert status.india_market.index_value == market._FALLBACK_QUOTES["^NSEI"][0]

    alerts = market._build_alerts(
        {**market._FALLBACK_QUOTES, "^GSPC": (5000.0, -100.0), "^VIX": (25.0, 3.0)}
    )
    assert alerts[0].type == "BEARISH"
    assert alerts[2].text.startswith("SENSEX")
    assert alerts[3].type == "VOLATILITY"
