import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from datetime import datetime
from sqlalchemy import select
from app.models.user import User
from app.models.research import ResearchReport
from app.models.signal import Signal as DBSignal
from app.models.stock import Stock
from app.api.v1.research import research_engine

@pytest.mark.asyncio
@patch("app.providers.yahoo.YahooFinanceProvider.get_historical_data")
@patch("app.providers.yahoo.YahooFinanceProvider.compute_metrics")
@patch("yfinance.Ticker")
async def test_end_to_end_flow(
    mock_ticker,
    mock_compute_metrics,
    mock_get_historical_data,
    client: AsyncClient,
    db_session
):
    # 1. Setup yfinance and OpenAI mocks
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.info = {
        "sector": "Technology",
        "trailingPE": 25.0,
        "priceToBook": 3.5,
        "priceToSalesTrailing12Months": 5.0
    }
    mock_ticker.return_value = mock_ticker_instance
    
    import pandas as pd
    mock_get_historical_data.return_value = pd.DataFrame({"Close": [100.0, 102.0]})
    mock_compute_metrics.return_value = {
        "historical_volatility": 0.22,
        "max_drawdown": -0.12,
        "total_return": 0.08,
        "beta": 1.25
    }
    
    # Mock LLM response
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """
    {
        "ticker": "AAPL",
        "summary": "Excellent growth profile with robust cash flow",
        "key_insights": ["Premium brand power", "Services revenue expanding"],
        "strengths": ["Ecosystem lock-in", "Strong balance sheet"],
        "weaknesses": ["Premium valuation", "Regulatory scrutiny"],
        "opportunities": ["AI integration", "Wearables expansion"],
        "threats": ["Intense competition", "Global supply chain risks"],
        "confidence_score": 90.0
    }
    """
    mock_llm.invoke.return_value = mock_response
    
    # Override the llm on the active research_engine instance
    with patch.object(research_engine.llm_orchestrator, "llm", mock_llm):
        # 2. Register user
        reg_payload = {"email": "e2e_user@quantara.com", "password": "securepassword123"}
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        token = reg_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Login
        login_payload = {"email": "e2e_user@quantara.com", "password": "securepassword123"}
        login_resp = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()
        
        # 4. Fetch profile
        profile_resp = await client.get("/api/v1/users/me", headers=headers)
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        assert profile_data["email"] == "e2e_user@quantara.com"
        assert profile_data["risk_level"] is None
        
        # 5. Update risk profile
        update_payload = {
            "risk_level": "Aggressive",
            "volatility_tolerance": 35.0,
            "investment_horizon": 36,
            "sector_preferences": {"Technology": 0.6, "Healthcare": 0.4}
        }
        update_resp = await client.post("/api/v1/users/risk-profile", json=update_payload, headers=headers)
        assert update_resp.status_code == 200
        updated_data = update_resp.json()
        assert updated_data["risk_level"] == "Aggressive"
        assert updated_data["volatility_tolerance"] == 35.0
        
        # 6. Generate stock research report
        research_resp = await client.get("/api/v1/stocks/AAPL/research", headers=headers)
        assert research_resp.status_code == 200
        research_data = research_resp.json()
        assert research_data["ticker"] == "AAPL"
        assert research_data["confidence_score"] == 90.0
        assert research_data["summary"] == "Excellent growth profile with robust cash flow"
        
        # Verify stock metadata is stored in DB
        stmt_stock = select(Stock).where(Stock.ticker == "AAPL")
        res_stock = await db_session.execute(stmt_stock)
        stock = res_stock.scalar_one_or_none()
        assert stock is not None
        assert stock.risk_score > 0
        assert stock.research_score == 90.0
        
        # Verify report is stored in DB
        stmt_report = select(ResearchReport).where(ResearchReport.ticker == "AAPL")
        res_report = await db_session.execute(stmt_report)
        report = res_report.scalar_one_or_none()
        assert report is not None
        
        # 7. Check cache: fetch research report again (mocks shouldn't be called this time)
        mock_llm.invoke.reset_mock()
        research_resp_cached = await client.get("/api/v1/stocks/AAPL/research", headers=headers)
        assert research_resp_cached.status_code == 200
        assert research_resp_cached.json()["ticker"] == "AAPL"
        mock_llm.invoke.assert_not_called()
        
        # 8. Verify signal endpoint returning signals
        db_signal = DBSignal(
            ticker="AAPL",
            signal_type="insider_buying",
            strength=85.0,
            confidence=95.0,
            data={"insiders": ["Tim Cook"]},
            timestamp=datetime.utcnow()
        )
        db_session.add(db_signal)
        await db_session.commit()
        
        signals_resp = await client.get("/api/v1/signals/?ticker=AAPL", headers=headers)
        assert signals_resp.status_code == 200
        signals_data = signals_resp.json()
        assert signals_data["total_count"] == 1
        assert signals_data["signals"][0]["ticker"] == "AAPL"
        assert signals_data["signals"][0]["signal_type"] == "insider_buying"
        
        # 9. Verify audit logs
        audit_resp = await client.get("/api/v1/audit/logs", headers=headers)
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()
        actions = [log["action"] for log in audit_data["logs"]]
        assert "register" in actions
        assert "login" in actions
        assert "update_profile" in actions
