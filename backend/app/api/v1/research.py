"""Research API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel

from app.core.dependencies import DBSession, CurrentUser
from app.services.research_engine import ResearchEngine

router = APIRouter()
research_engine = ResearchEngine()


class ResearchReportResponse(BaseModel):
    """Research report response schema."""
    ticker: str
    summary: str
    key_insights: list[str]
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
    confidence_score: float


class StockSearchItem(BaseModel):
    """Stock item schema for explorer list."""
    ticker: str
    name: str
    price: str
    cap: str
    risk: float
    signal: str
    alpha: str
    status: str


class StockSearchListResponse(BaseModel):
    """Stock search list response schema."""
    stocks: list[StockSearchItem]
    total_count: int


@router.get("/stocks/search", response_model=StockSearchListResponse)
async def search_stocks(
    current_user: CurrentUser,
    db: DBSession,
    query: Optional[str] = None,
    pe_min: Optional[float] = None,
    pe_max: Optional[float] = None,
    beta_min: Optional[float] = None,
    beta_max: Optional[float] = None,
    risk_min: Optional[float] = None,
    risk_max: Optional[float] = None,
    signals: Optional[str] = None,
) -> StockSearchListResponse:
    """
    Search stocks with criteria filters.
    """
    from app.models.stock import Stock
    from app.models.signal import Signal
    from sqlalchemy import select, or_
    
    stmt = select(Stock)
    
    # 1. Join with signals if signal filters applied
    if signals:
        signal_list = [s.strip().lower() for s in signals.split(",") if s.strip()]
        if signal_list:
            mapped_types = []
            for s in signal_list:
                if "inflow" in s or "institutional" in s:
                    mapped_types.append("institutional_buying")
                elif "insider" in s:
                    mapped_types.append("insider_buying")
                elif "options" in s or "vol" in s or "sentiment" in s:
                    mapped_types.append("sentiment_spike")
            
            if mapped_types:
                sig_stmt = select(Signal.ticker).where(Signal.signal_type.in_(mapped_types))
                sig_res = await db.execute(sig_stmt)
                matching_tickers = {r for r in sig_res.scalars().all()}
                stmt = stmt.where(Stock.ticker.in_(matching_tickers))
                
    if query:
        stmt = stmt.where(
            or_(
                Stock.ticker.ilike(f"%{query}%"),
                Stock.name.ilike(f"%{query}%")
            )
        )
    if pe_min is not None:
        stmt = stmt.where(Stock.pe_ratio >= pe_min)
    if pe_max is not None:
        stmt = stmt.where(Stock.pe_ratio <= pe_max)
    if beta_min is not None:
        stmt = stmt.where(Stock.beta >= beta_min)
    if beta_max is not None:
        stmt = stmt.where(Stock.beta <= beta_max)
    if risk_min is not None:
        stmt = stmt.where(Stock.risk_score >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Stock.risk_score <= risk_max)
        
    result = await db.execute(stmt)
    db_stocks = result.scalars().all()
    
    response_items = []
    for stock in db_stocks:
        sig_str = "Neutral"
        if stock.research_score is not None:
            if stock.research_score >= 88:
                sig_str = "Strong"
            elif stock.research_score >= 70:
                sig_str = "High"
            elif stock.research_score < 40:
                sig_str = "Weak"
                
        response_items.append(
            StockSearchItem(
                ticker=stock.ticker,
                name=stock.name or stock.ticker,
                price=stock.price or "$0.00",
                cap=stock.market_cap or "0.0B",
                risk=stock.risk_score or 50.0,
                signal=sig_str,
                alpha=stock.alpha_projection or "+0.0%",
                status=stock.status or "neutral"
            )
        )
        
    return StockSearchListResponse(
        stocks=response_items,
        total_count=len(response_items)
    )


@router.get("/stocks/{ticker}/research", response_model=ResearchReportResponse)
async def get_stock_research(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
    x_openai_api_key: Optional[str] = Header(None, alias="X-OpenAI-API-Key"),
    x_sec_user_agent: Optional[str] = Header(None, alias="X-SEC-User-Agent"),
) -> ResearchReportResponse:
    """
    Get research report for a stock.
    
    Args:
        ticker: Stock ticker symbol
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Research report
    """
    from app.models.research import ResearchReport
    from sqlalchemy import select
    
    ticker_upper = ticker.upper()
    
    # Check cache / database first
    stmt = select(ResearchReport).where(ResearchReport.ticker == ticker_upper)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if report and report.structured_json:
        return ResearchReportResponse(**report.structured_json)
        
    # Generate new report
    report_data = await research_engine.generate_research_report(
        db, ticker_upper, openai_api_key=x_openai_api_key, sec_user_agent=x_sec_user_agent
    )
    
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate research report for {ticker}",
        )
    
    return ResearchReportResponse(**report_data)
