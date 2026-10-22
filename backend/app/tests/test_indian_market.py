"""Tests for Indian Market (NSE/BSE) Support in Quantara.

Covers:
- Stock search filtering by market (india, us, all)
- Dual market status (US S&P/VIX and India NIFTY/India VIX)
- Macroeconomic stress testing scenarios for Indian equities
- Peer correlation and benchmark attribution for Indian tickers
- SEC EDGAR graceful bypass for Indian exchanges (.NS, .BO)
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.api.v1.research import search_stocks
from app.api.v1.market import get_market_status
from app.api.v1.risk import get_stock_scenarios, get_stock_correlations
from app.models.stock import Stock
from app.providers.sec import SECProvider
from app.services.risk_engine import RiskEngine


@pytest.mark.asyncio
async def test_stock_search_market_filter():
    """Test stock search filtering by market parameter."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    reliance = Stock(
        ticker="RELIANCE.NS",
        name="Reliance Industries Ltd",
        price="₹1,215.40",
        market_cap="18.5T",
        risk_score=34.0,
        research_score=92.0,
        alpha_projection="+14.8%",
        status="up",
    )
    nvda = Stock(
        ticker="NVDA",
        name="NVIDIA Corporation",
        price="$120.50",
        market_cap="$3.0T",
        risk_score=72.0,
        research_score=85.0,
        alpha_projection="+14.2%",
        status="up",
    )

    # When market=india, mock return only reliance
    mock_result.scalars.return_value.all.return_value = [reliance]
    mock_db.execute.return_value = mock_result
    current_user = {"id": "1", "email": "analyst@quantara.com"}

    resp_in = await search_stocks(current_user=current_user, db=mock_db, market="india")
    assert resp_in.total_count == 1
    assert resp_in.stocks[0].ticker == "RELIANCE.NS"
    assert "₹" in resp_in.stocks[0].price

    # When market=us, mock return only nvda
    mock_result.scalars.return_value.all.return_value = [nvda]
    resp_us = await search_stocks(current_user=current_user, db=mock_db, market="us")
    assert resp_us.total_count == 1
    assert resp_us.stocks[0].ticker == "NVDA"
    assert "$" in resp_us.stocks[0].price


@pytest.mark.asyncio
async def test_dual_market_status():
    """Test market status endpoint returning US and India payloads."""
    status = await get_market_status()
    assert status.vix.value > 0

    # US Market checks
    assert status.us_market is not None
    assert status.us_market.country == "United States"
    assert status.us_market.index_value > 0
    assert status.us_market.vix > 0
    assert status.us_market.status in ["OPEN", "CLOSED"]

    # India Market checks
    assert status.india_market is not None
    assert status.india_market.country == "India"
    assert status.india_market.index_name == "NIFTY 50"
    assert status.india_market.index_value > 20000
    assert status.india_market.vix > 0
    assert status.india_market.status in ["OPEN", "CLOSED"]


def test_indian_macro_stress_scenarios():
    """Test that Indian equities receive tailored RBI, crude, capex, and monsoon scenarios."""
    engine = RiskEngine()
    scenarios = engine.run_scenario_stress_test(
        ticker="RELIANCE.NS",
        beta=1.05,
        pe_ratio=24.5,
        debt_to_equity=0.45,
        sector="Energy",
    )

    assert len(scenarios) == 6
    scenario_ids = [s["id"] for s in scenarios]
    assert "rbi_repo_rate_hike_50bps" in scenario_ids
    assert "crude_spike_100_inr_depreciation" in scenario_ids
    assert "india_capex_cycle_acceleration" in scenario_ids
    assert "monsoon_deficit_rural_slowdown" in scenario_ids
    assert "global_tech_slowdown" in scenario_ids
    assert "domestic_credit_spread_widening" in scenario_ids

    # For an energy giant like Reliance, crude spike should have positive/hedging energy factor
    crude_scen = next(s for s in scenarios if s["id"] == "crude_spike_100_inr_depreciation")
    assert crude_scen["name"] == "Brent Crude $100 + INR Depreciation"
    assert "oil_beta" in crude_scen["factor_breakdown"]


@pytest.mark.asyncio
async def test_indian_peer_correlation_and_benchmark(monkeypatch):
    """Test correlation endpoint uses NIFTY 50 and Indian peers for .NS tickers."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = Stock(
        ticker="TCS.NS",
        name="Tata Consultancy Services Ltd",
        sector="Technology",
        beta=0.85,
        pe_ratio=28.0,
    )
    peers_res = MagicMock()
    peers_res.scalars.return_value.all.return_value = [
        Stock(ticker="INFY.NS", name="Infosys Ltd", sector="Technology", beta=0.95),
        Stock(ticker="HDFCBANK.NS", name="HDFC Bank Ltd", sector="Financials", beta=1.10),
    ]
    mock_db.execute.side_effect = [mock_res, peers_res]
    current_user = {"id": "1", "email": "analyst@quantara.com"}

    from app.api.v1 import risk

    def offline(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(risk.yf, "download", offline)
    corr = await get_stock_correlations(ticker="TCS.NS", current_user=current_user, db=mock_db)
    assert corr.benchmark_ticker == "NIFTY 50"
    assert len(corr.peers) > 0
    peer_tickers = [p.ticker for p in corr.peers]
    assert peer_tickers[0] == "INFY.NS"  # same-sector peer first
    assert "GOLDBEES.NS" in peer_tickers


@pytest.mark.asyncio
async def test_sec_provider_indian_exchange_bypass():
    """Test SEC provider gracefully returns None/empty for Indian exchange tickers."""
    provider = SECProvider()

    # Async CIK lookup
    cik_ns = await provider.get_cik_async("RELIANCE.NS")
    assert cik_ns is None

    cik_bo = await provider.get_cik_async("TCS.BO")
    assert cik_bo is None

    # Sync CIK lookup
    assert provider.get_cik("INFY.NS") is None

    # Company facts and insider transactions
    facts = await provider.fetch_company_facts("HDFCBANK.NS")
    assert facts is None

    insiders = await provider.fetch_insider_transactions("RELIANCE.NS")
    assert insiders == []


@pytest.mark.asyncio
async def test_yahoo_fundamentals_feed_nse_bse_research(monkeypatch):
    """NSE/BSE tickers get statement fundamentals from Yahoo in SEC metric shape."""
    import pandas as pd

    from app.providers import yahoo as yahoo_mod
    from app.services.llm_orchestrator import LLMOrchestrator

    annual = pd.to_datetime(["2024-03-31", "2025-03-31"])
    fake = MagicMock()
    fake.income_stmt = pd.DataFrame(
        {annual[0]: [900.0, 90.0], annual[1]: [1000.0, 120.0]},
        index=["Total Revenue", "Net Income"],
    )
    fake.balance_sheet = pd.DataFrame(
        {annual[1]: [5000.0, 1000.0]}, index=["Total Assets", "Total Debt"]
    )
    fake.cashflow = pd.DataFrame()
    fake.quarterly_income_stmt = pd.DataFrame(
        {pd.Timestamp("2025-06-30"): [35.0]}, index=["Net Income"]
    )
    monkeypatch.setattr(yahoo_mod.yf, "Ticker", lambda symbol: fake)

    metrics = await yahoo_mod.YahooFinanceProvider().get_fundamentals("TCS.BO")
    assert [r["val"] for r in metrics["revenue"]] == [900.0, 1000.0]
    assert [r["form"] for r in metrics["net_income"]] == ["10-K", "10-K", "10-Q"]
    assert metrics["cash_flow"] == []

    orchestrator = LLMOrchestrator.__new__(LLMOrchestrator)
    sec = MagicMock()
    sec.fetch_company_facts = AsyncMock(return_value=None)
    orchestrator._get_sec_provider = lambda ua: sec
    state = await orchestrator._retrieve_data({"ticker": "TCS.BO"})
    assert state["raw_data"]["source"] == "Yahoo Finance (BSE)"
    # Latest financials use the annual figure, not the newer quarter
    assert state["raw_data"]["financials"]["net_income"] == 120.0
    assert state["raw_data"]["financials"]["total_debt"] == 1000.0
