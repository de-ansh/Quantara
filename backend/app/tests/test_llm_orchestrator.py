import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import pandas as pd
from app.services.llm_orchestrator import LLMOrchestrator, AnalysisState
from app.models.stock import Stock
from app.models.research import ResearchReport
from sqlalchemy import select

@pytest.fixture
def orchestrator():
    with patch("app.services.llm_orchestrator.ChatOpenAI"):
        yield LLMOrchestrator()

@pytest.fixture
def sample_state():
    return {
        "ticker": "AAPL",
        "raw_data": {
            "financials": {
                "revenue": 100000000.0,
                "net_income": 20000000.0,
                "total_assets": 150000000.0,
                "total_debt": 50000000.0,
            },
            "historical_metrics": {
                "revenue": [
                    {"val": 80000000.0, "form": "10-K", "end": "2022-12-31"},
                    {"val": 100000000.0, "form": "10-K", "end": "2023-12-31"}
                ],
                "net_income": [
                    {"val": 15000000.0, "form": "10-Q", "end": "2023-03-31"},
                    {"val": 20000000.0, "form": "10-Q", "end": "2023-06-31"}
                ]
            },
            "sector": "Technology",
            "pe_ratio": 25.0,
            "price_to_book": 3.5,
            "price_to_sales": 5.0,
        },
        "computed_metrics": {},
        "risk_classification": {},
        "structured_analysis": {},
        "validation_errors": [],
        "retry_count": 0,
        "final_output": None,
        "db": None,
    }

@pytest.mark.asyncio
@patch("app.providers.yahoo.YahooFinanceProvider.get_historical_data")
@patch("app.providers.yahoo.YahooFinanceProvider.compute_metrics")
@patch("yfinance.Ticker")
async def test_compute_metrics_node(mock_ticker, mock_compute_metrics, mock_get_historical_data, orchestrator, sample_state):
    # Mock Yahoo Finance
    mock_get_historical_data.return_value = pd.DataFrame({"Close": [100.0, 102.0]})
    mock_compute_metrics.return_value = {
        "historical_volatility": 0.2,
        "max_drawdown": -0.1,
        "total_return": 0.05,
        "beta": 1.1
    }
    
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 25.0, "priceToBook": 3.5, "priceToSalesTrailing12Months": 5.0}
    mock_ticker.return_value = mock_ticker_instance
    
    res_state = await orchestrator._compute_metrics(sample_state)
    
    assert res_state["computed_metrics"]["revenue_growth"] == pytest.approx(0.25)
    assert res_state["computed_metrics"]["profit_margin"] == pytest.approx(0.2)
    assert res_state["computed_metrics"]["roe"] == pytest.approx(0.2)
    assert res_state["computed_metrics"]["historical_volatility"] == 0.2
    assert res_state["computed_metrics"]["beta"] == 1.1

@pytest.mark.asyncio
async def test_risk_classification_node(orchestrator, sample_state):
    sample_state["computed_metrics"] = {
        "historical_volatility": 0.2,
        "beta": 1.1,
    }
    
    res_state = await orchestrator._risk_classification(sample_state)
    
    risk_info = res_state["risk_classification"]
    assert "risk_score" in risk_info
    assert "risk_level" in risk_info
    assert risk_info["risk_level"] in ["Conservative", "Moderate", "Aggressive"]
    assert "components" in risk_info

@pytest.mark.asyncio
async def test_store_result_node(db_session, orchestrator, sample_state):
    sample_state["db"] = db_session
    sample_state["risk_classification"] = {
        "risk_score": 62.5,
    }
    sample_state["final_output"] = {
        "ticker": "AAPL",
        "summary": "Strong fundamentals",
        "key_insights": ["Insight 1"],
        "strengths": ["Brand"],
        "weaknesses": ["Valuation"],
        "opportunities": ["AI"],
        "threats": ["Competition"],
        "confidence_score": 85.0
    }
    
    res_state = await orchestrator._store_result(sample_state)
    
    # Verify stock table updated
    stmt_stock = select(Stock).where(Stock.ticker == "AAPL")
    res_stock = await db_session.execute(stmt_stock)
    stock = res_stock.scalar_one_or_none()
    assert stock is not None
    assert stock.risk_score == 62.5
    assert stock.research_score == 85.0
    assert stock.sector == "Technology"
    
    # Verify research report saved
    stmt_report = select(ResearchReport).where(ResearchReport.ticker == "AAPL")
    res_report = await db_session.execute(stmt_report)
    report = res_report.scalar_one_or_none()
    assert report is not None
    assert report.confidence_score == 85.0
    assert report.structured_json["summary"] == "Strong fundamentals"
