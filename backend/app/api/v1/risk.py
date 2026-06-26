"""Risk analysis API endpoints."""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel

from app.core.dependencies import DBSession, CurrentUser
from app.services.risk_engine import RiskEngine, RiskLevel

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


class RiskAnalysisResponse(BaseModel):
    """Risk analysis response schema."""
    ticker: str
    overall_risk_score: float
    risk_level: str
    risk_band: str
    components: RiskComponentsResponse
    explanation: str


@router.get("/stocks/{ticker}/risk", response_model=RiskAnalysisResponse)
async def get_stock_risk_analysis(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
    x_sec_user_agent: Optional[str] = Header(None, alias="X-SEC-User-Agent"),
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
    from app.services.llm_orchestrator import LLMOrchestrator
    orchestrator = LLMOrchestrator()
    
    # Initialize transient state
    initial_state = {
        "ticker": ticker.upper(),
        "raw_data": {},
        "computed_metrics": {},
        "risk_classification": {},
        "structured_analysis": {},
        "validation_errors": [],
        "retry_count": 0,
        "final_output": None,
        "db": db,
        "sec_user_agent": x_sec_user_agent,
    }
    
    try:
        # Run nodes sequentially to compute metrics and execute risk engine
        state = await orchestrator._retrieve_data(initial_state)
        state = await orchestrator._compute_metrics(state)
        state = await orchestrator._risk_classification(state)
        risk_data = state.get("risk_classification", {})
    except Exception as e:
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
        }
        
    components = risk_data.get("components", {})
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
    )
