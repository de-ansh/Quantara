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
        "sector_preferences": {"Technology": 50.0, "Healthcare": 20.0}
    }
    post_resp = await client.post("/api/v1/users/risk-profile", json=update_payload, headers=headers)
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
async def test_custom_headers_parsing(client: AsyncClient):
    """Test that custom headers are accepted by the endpoints without breaking."""
    reg_payload = {"email": "headers_user@quantara.com", "password": "securepassword123"}
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    token = login_resp.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-OpenAI-API-Key": "sk-proj-testkeyoverride12345",
        "X-SEC-User-Agent": "TestAgent Override contact@test.com"
    }

    # Verify custom user agent header on risk analysis (triggers _retrieve_data nodes)
    resp = await client.get("/api/v1/stocks/AAPL/risk", headers=headers)
    # Regardless of actual external API result (which might fallback), the endpoint itself should not raise a 500 error due to headers.
    assert resp.status_code == 200
