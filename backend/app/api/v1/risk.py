"""Risk analysis API endpoints."""

import asyncio
import time
from typing import Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUser, DBSession
from app.core.logging import get_logger
from app.services.risk_engine import RiskEngine

logger = get_logger(__name__)
router = APIRouter()
risk_engine = RiskEngine()


class RiskComponentsResponse(BaseModel):
    """Risk components response schema."""

    volatility_score: float
    beta_score: float
    leverage_score: float
    earnings_stability_score: float
    sector_risk_score: float
    valuation_risk_score: float


class DrawdownPoint(BaseModel):
    """Drawdown data point schema."""

    time: str
    historical: float | None = None
    projected: float | None = None
    drawdown_pct: float | None = None


class ScenarioStressResult(BaseModel):
    """Macro stress test scenario response schema."""

    id: str
    name: str
    type: str
    impact_pct: float
    status: str
    factor_breakdown: dict[str, float] = {}
    narrative: str | None = None


class RiskAnalysisResponse(BaseModel):
    """Risk analysis response schema."""

    ticker: str
    overall_risk_score: float
    risk_level: str
    risk_band: str
    components: RiskComponentsResponse
    explanation: str
    max_drawdown: float = 0.0
    drawdown_series: list[DrawdownPoint] = []
    scenarios: list[ScenarioStressResult] = []
    factor_sensitivities: dict[str, float] = {}
    assumed_inputs: list[str] = Field(
        default_factory=list,
        description="Inputs that were unavailable and replaced by defaults; results using them are estimates",
    )


@router.get("/stocks/{ticker}/risk", response_model=RiskAnalysisResponse)
async def get_stock_risk_analysis(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
) -> RiskAnalysisResponse:
    """
    Get risk analysis for a stock.

    Args:
        ticker: Stock ticker symbol
        current_user: Authenticated user
        db: Database session

    Returns:
        Risk analysis
    """
    # Fetch actual financial data and execute deterministic risk engine
    from app.services.llm_orchestrator import AnalysisState, LLMOrchestrator

    orchestrator = LLMOrchestrator()

    # Initialize transient state
    initial_state: AnalysisState = {
        "ticker": ticker.upper(),
        "raw_data": {},
        "computed_metrics": {},
        "risk_classification": {},
        "structured_analysis": {},
        "validation_errors": [],
        "retry_count": 0,
        "final_output": None,
        "db": db,
        "openai_api_key": None,
        "sec_user_agent": current_user["sec_user_agent"],
    }

    state: AnalysisState | None = None
    try:
        # Run nodes sequentially to compute metrics and execute risk engine
        state = await orchestrator._retrieve_data(initial_state)
        state = await orchestrator._compute_metrics(state)
        state = await orchestrator._risk_classification(state)
        risk_data = state.get("risk_classification", {})
    except Exception:
        state = None
        # Graceful fallback if external APIs or calculations fail
        from app.services.risk_engine import RiskEngine

        engine = RiskEngine()
        analysis = engine.analyze_stock_risk(
            ticker=ticker.upper(),
            historical_volatility=0.25,
            beta=1.2,
            debt_to_equity=0.5,
            earnings_volatility=0.15,
            consecutive_profitable_quarters=8,
            sector="Technology",
            pe_ratio=25.0,
            price_to_book=3.5,
        )
        drawdown_val, drawdown_series = engine.generate_drawdown_series(
            df=None,
            historical_volatility=0.25,
            overall_risk_score=analysis.overall_risk_score,
            max_drawdown=-0.25,
        )
        risk_data = {
            "risk_score": analysis.overall_risk_score,
            "risk_level": analysis.risk_level.value,
            "risk_band": analysis.risk_band,
            "components": {
                "volatility_score": analysis.components.volatility_score,
                "beta_score": analysis.components.beta_score,
                "leverage_score": analysis.components.leverage_score,
                "earnings_stability_score": analysis.components.earnings_stability_score,
                "sector_risk_score": analysis.components.sector_risk_score,
                "valuation_risk_score": analysis.components.valuation_risk_score,
            },
            "explanation": analysis.explanation,
            "max_drawdown": drawdown_val,
            "drawdown_series": drawdown_series,
        }

    components = risk_data.get("components", {})

    # Compute quantitative factor sensitivities and scenario stress tests
    # Real inputs where available; each default used is reported in `assumed_inputs`.
    metrics = state.get("computed_metrics", {}) if state else {}
    raw = state.get("raw_data", {}) if state else {}
    actual = {
        "beta": metrics.get("beta"),
        "pe_ratio": raw.get("pe_ratio"),
        "debt_to_equity": metrics.get("debt_to_equity"),
        "sector": raw.get("sector") if raw.get("sector") not in (None, "", "Unknown") else None,
    }
    defaults: dict[str, Any] = {
        "beta": 1.1,
        "pe_ratio": 25.0,
        "debt_to_equity": 0.5,
        "sector": "Technology",
    }
    assumed = [k for k, v in actual.items() if v is None]
    if state is None:
        assumed.insert(0, "price_history")
    stock_beta = actual["beta"] if actual["beta"] is not None else defaults["beta"]
    stock_pe = actual["pe_ratio"] if actual["pe_ratio"] is not None else defaults["pe_ratio"]
    stock_de = (
        actual["debt_to_equity"]
        if actual["debt_to_equity"] is not None
        else defaults["debt_to_equity"]
    )
    stock_sector = actual["sector"] or defaults["sector"]

    factor_sens = risk_engine.calculate_factor_sensitivities(
        ticker=ticker.upper(),
        beta=stock_beta,
        pe_ratio=stock_pe,
        debt_to_equity=stock_de,
        sector=stock_sector,
    )
    # Drop sensitivities that would be derived from an assumed input
    depends_on = {
        "market_beta": {"beta"},
        "interest_rate_beta": {"pe_ratio", "debt_to_equity"},
        "credit_spread_beta": {"debt_to_equity"},
        "oil_beta": {"sector"},
        "tech_momentum_beta": {"sector", "beta"},
    }
    factor_sens = {
        k: v for k, v in factor_sens.items() if not depends_on.get(k, set()) & set(assumed)
    }
    scenarios_data = risk_engine.run_scenario_stress_test(
        ticker=ticker.upper(),
        beta=stock_beta,
        pe_ratio=stock_pe,
        debt_to_equity=stock_de,
        sector=stock_sector,
    )

    return RiskAnalysisResponse(
        ticker=ticker.upper(),
        overall_risk_score=risk_data.get("risk_score", 50.0),
        risk_level=risk_data.get("risk_level", "Moderate"),
        risk_band=risk_data.get("risk_band", "34-66"),
        components=RiskComponentsResponse(
            volatility_score=components.get("volatility_score", 50.0),
            beta_score=components.get("beta_score", 50.0),
            leverage_score=components.get("leverage_score", 50.0),
            earnings_stability_score=components.get("earnings_stability_score", 50.0),
            sector_risk_score=components.get("sector_risk_score", 50.0),
            valuation_risk_score=components.get("valuation_risk_score", 50.0),
        ),
        explanation=risk_data.get("explanation", ""),
        max_drawdown=risk_data.get("max_drawdown", 0.0),
        drawdown_series=risk_data.get("drawdown_series", []),
        scenarios=[ScenarioStressResult(**s) for s in scenarios_data],
        factor_sensitivities=factor_sens,
        assumed_inputs=assumed,
    )


@router.get("/stocks/{ticker}/scenarios", response_model=list[ScenarioStressResult])
async def get_stock_scenarios(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
) -> list[ScenarioStressResult]:
    """
    Get multi-factor macroeconomic stress test scenarios for a stock.

    Args:
        ticker: Stock ticker symbol
        current_user: Authenticated user
        db: Database session

    Returns:
        List of macro scenario stress test results with factor breakdown.
    """
    from sqlalchemy import select

    from app.models.stock import Stock

    stmt = select(Stock).where(Stock.ticker == ticker.upper())
    res = await db.execute(stmt)
    stock = res.scalar_one_or_none()

    beta = stock.beta if stock and stock.beta is not None else 1.1
    pe_ratio = stock.pe_ratio if stock and stock.pe_ratio is not None else 25.0
    sector = stock.sector if stock and stock.sector else "Technology"

    scenarios = risk_engine.run_scenario_stress_test(
        ticker=ticker.upper(),
        beta=beta,
        pe_ratio=pe_ratio,
        debt_to_equity=0.5,
        sector=sector,
    )
    return [ScenarioStressResult(**s) for s in scenarios]


class PeerCorrelation(BaseModel):
    """Peer correlation response schema."""

    ticker: str
    name: str
    sector: str
    correlation: float
    beta: float
    relationship: str


class StockCorrelationResponse(BaseModel):
    """Stock correlation response schema."""

    ticker: str
    sector: str
    benchmark_ticker: str = "S&P 500"
    benchmark_correlation: float
    peers: list[PeerCorrelation]


@router.get("/stocks/{ticker}/correlation", response_model=StockCorrelationResponse)
async def get_stock_correlations(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
) -> StockCorrelationResponse:
    """
    Get dynamic cross-asset and sector peer correlations for a stock.

    Args:
        ticker: Stock ticker symbol
        current_user: Authenticated user
        db: Database session

    Returns:
        Structured correlation dataset with sector peers and macro hedges
    """
    from sqlalchemy import and_, or_, select

    from app.models.stock import Stock
    from app.services.portfolio_analytics import PortfolioAnalyticsEngine

    ticker_upper = ticker.upper()

    # Query active stock to determine sector and beta
    stmt = select(Stock).where(Stock.ticker == ticker_upper)
    res = await db.execute(stmt)
    stock = res.scalar_one_or_none()

    active_sector = stock.sector if stock and stock.sector else "Technology"
    active_beta = stock.beta if stock and stock.beta else 1.1

    is_indian = ticker_upper.endswith((".NS", ".BO"))
    benchmark = "^NSEI" if is_indian else "^GSPC"

    # Equity peers come from the stocks table, same market, same-sector first
    market_filter = (
        or_(Stock.ticker.ilike("%.NS"), Stock.ticker.ilike("%.BO"))
        if is_indian
        else and_(~Stock.ticker.ilike("%.NS"), ~Stock.ticker.ilike("%.BO"))
    )
    peer_rows = (
        (await db.execute(select(Stock).where(market_filter, Stock.ticker != ticker_upper)))
        .scalars()
        .all()
    )
    candidates = [
        {
            "ticker": p.ticker,
            "name": p.name or p.ticker,
            "sector": p.sector or "Unknown",
            "beta": p.beta or 1.0,
        }
        for p in sorted(peer_rows, key=lambda p: p.sector != active_sector)
    ][:9] + [
        h for h in HEDGE_INSTRUMENTS["india" if is_indian else "us"] if h["ticker"] != ticker_upper
    ]

    returns = await _get_daily_returns(
        tuple([ticker_upper, benchmark] + [c["ticker"] for c in candidates])
    )

    def _real_corr(a: str, b: str) -> float | None:
        if returns is None or a not in returns or b not in returns:
            return None
        pair = returns[[a, b]].dropna()
        if len(pair) < MIN_OVERLAP_DAYS:
            return None
        value = pair[a].corr(pair[b])
        return None if pd.isna(value) else float(value)

    def _real_beta(t: str) -> float | None:
        if returns is None or t not in returns or benchmark not in returns:
            return None
        pair = returns[[t, benchmark]].dropna()
        if len(pair) < MIN_OVERLAP_DAYS or pair[benchmark].var() == 0:
            return None
        return float(pair[t].cov(pair[benchmark]) / pair[benchmark].var())

    peers: list[PeerCorrelation] = []
    for cand in candidates:
        corr = _real_corr(ticker_upper, cand["ticker"])
        if corr is None:
            corr = PortfolioAnalyticsEngine.estimate_pairwise_correlation(
                ticker_upper, cand["ticker"], sector_a=active_sector, sector_b=cand["sector"]
            )

        if cand["sector"] == active_sector:
            rel = "Direct Sector Peer"
        elif cand["sector"] in ("Fixed Income", "Commodities", "Cash"):
            rel = "Macro / Risk Hedge" if corr <= 0 else "Low Correlation Asset"
        else:
            rel = "Cross-Sector Equity"

        beta = _real_beta(cand["ticker"])
        peers.append(
            PeerCorrelation(
                ticker=cand["ticker"],
                name=cand["name"],
                sector=cand["sector"],
                correlation=round(corr, 2),
                beta=round(beta, 2) if beta is not None else cand["beta"],
                relationship=rel,
            )
        )

    benchmark_corr = _real_corr(ticker_upper, benchmark)
    if benchmark_corr is None:
        # No usable price history: estimate from beta
        benchmark_corr = min(0.95, max(0.10, 0.55 + (active_beta - 1.0) * 0.25))

    return StockCorrelationResponse(
        ticker=ticker_upper,
        sector=active_sector,
        benchmark_ticker="NIFTY 50" if is_indian else "S&P 500",
        benchmark_correlation=round(benchmark_corr, 2),
        peers=peers,
    )


# Non-equity diversifiers shown beside equity peers; a product choice, not market data
HEDGE_INSTRUMENTS: dict[str, list[dict[str, Any]]] = {
    "india": [
        {
            "ticker": "GOLDBEES.NS",
            "name": "Nippon India ETF Gold BeES",
            "sector": "Commodities",
            "beta": 0.05,
        },
        {
            "ticker": "LIQUIDBEES.NS",
            "name": "Nippon India ETF Liquid BeES",
            "sector": "Cash",
            "beta": 0.0,
        },
    ],
    "us": [
        {
            "ticker": "TLT",
            "name": "20+ Year Treasury Bond ETF",
            "sector": "Fixed Income",
            "beta": 0.15,
        },
        {"ticker": "GLD", "name": "SPDR Gold Shares", "sector": "Commodities", "beta": 0.05},
        {"ticker": "BIL", "name": "SPDR 1-3M T-Bill (Cash)", "sector": "Cash", "beta": 0.0},
    ],
}
MIN_OVERLAP_DAYS = 60
_RETURNS_TTL_SECONDS = 24 * 3600.0
_returns_cache: dict[tuple[str, ...], tuple[float, pd.DataFrame | None]] = {}


async def _get_daily_returns(tickers: tuple[str, ...]) -> pd.DataFrame | None:
    """One year of daily returns per ticker (columns), cached for a day; None if Yahoo fails."""
    cached = _returns_cache.get(tickers)
    if cached and time.monotonic() - cached[0] < _RETURNS_TTL_SECONDS:
        return cached[1]

    def _download() -> pd.DataFrame | None:
        closes = yf.download(
            list(tickers), period="1y", interval="1d", auto_adjust=True, progress=False
        )["Close"]
        if isinstance(closes, pd.Series):
            closes = closes.to_frame(tickers[0])
        return closes.pct_change(fill_method=None).dropna(how="all")

    try:
        returns = await asyncio.to_thread(_download)
    except Exception as e:
        logger.warning(f"Price history download failed for correlations: {e}")
        return None  # don't cache failures, retry next request
    _returns_cache[tickers] = (time.monotonic(), returns)
    return returns
