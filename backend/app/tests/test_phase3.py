import pytest
from httpx import AsyncClient
from app.models.stock import Stock
from sqlalchemy import select

@pytest.mark.asyncio
async def test_stocks_search_endpoint(client: AsyncClient, db_session):
    # Ensure database seeding occurred on lifespan/startup or seed manually for test
    # (FastAPI tests might bypass lifespan depending on setup, let's ensure we seed manually)
    db_session.add(
        Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", risk_score=14.0, research_score=85.0, price="$189.42", market_cap="2.94T", pe_ratio=25.0, beta=1.1, status="up", alpha_projection="+12.4%")
    )
    db_session.add(
        Stock(ticker="TSLA", name="Tesla Inc.", sector="Consumer Discretionary", risk_score=72.0, research_score=60.0, price="$175.22", market_cap="558.2B", pe_ratio=60.0, beta=1.5, status="down", alpha_projection="-4.2%")
    )
    await db_session.commit()

    # Get authentication token
    reg_payload = {"email": "phase3_user@quantara.com", "password": "securepassword123"}
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test search all
    resp = await client.get("/api/v1/stocks/search", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 2
    tickers = [s["ticker"] for s in data["stocks"]]
    assert "AAPL" in tickers
    assert "TSLA" in tickers

    # Test query filter
    resp = await client.get("/api/v1/stocks/search?query=Apple", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["stocks"][0]["ticker"] == "AAPL"

    # Test P/E max filter
    resp = await client.get("/api/v1/stocks/search?pe_max=30", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    tickers_pe = [s["ticker"] for s in data["stocks"]]
    assert "AAPL" in tickers_pe
    assert "TSLA" not in tickers_pe


@pytest.mark.asyncio
async def test_dynamic_risk_analysis_endpoint(client: AsyncClient, db_session):
    # Register/Login
    reg_payload = {"email": "risk_user@quantara.com", "password": "securepassword123"}
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch risk for AAPL (uses fallback/computed metrics in test environment)
    resp = await client.get("/api/v1/stocks/AAPL/risk", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert "overall_risk_score" in data
    assert "risk_level" in data
    assert "components" in data
    assert "volatility_score" in data["components"]


@pytest.mark.asyncio
async def test_portfolio_simulation_trajectory_endpoint(client: AsyncClient, db_session):
    # Register/Login
    reg_payload = {"email": "sim_user@quantara.com", "password": "securepassword123"}
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post("/api/v1/auth/login", json=reg_payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Post simulation payload
    payload = {
        "stocks": [
            {"ticker": "AAPL", "weight": 0.6},
            {"ticker": "TLT", "weight": 0.4}
        ],
        "initial_investment": 1000000.0,
        "time_horizon_months": 12
    }

    resp = await client.post("/api/v1/portfolio/simulate", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "expected_return" in data
    assert "expected_volatility" in data
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert "trajectory" in data
    assert len(data["trajectory"]) == 13 # 0 to 12 months
    assert data["trajectory"][0]["month"] == 0
    assert data["trajectory"][0]["median"] == 1000000.0
