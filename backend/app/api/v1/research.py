"""Research API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
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


@router.get("/stocks/{ticker}/research", response_model=ResearchReportResponse)
async def get_stock_research(
    ticker: str,
    current_user: CurrentUser,
    db: DBSession,
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
    # TODO: Check cache first
    # TODO: Fetch from database if exists
    
    # Generate new report
    report = await research_engine.generate_research_report(ticker.upper())
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate research report for {ticker}",
        )
    
    return ResearchReportResponse(**report)
