"""Portfolio simulation API endpoints."""
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.dependencies import DBSession, CurrentUser

router = APIRouter()


class PortfolioStock(BaseModel):
    """Portfolio stock schema."""
    ticker: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight (0-1)")


class SimulationRequest(BaseModel):
    """Portfolio simulation request schema."""
    stocks: List[PortfolioStock]
    initial_investment: float = Field(..., gt=0)
    time_horizon_months: int = Field(..., ge=1, le=360)


class TrajectoryPoint(BaseModel):
    """Monte Carlo trajectory point."""
    month: int
    median: float
    upper_95: float
    lower_5: float


class SimulationResult(BaseModel):
    """Portfolio simulation result schema."""
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    risk_adjusted_return: float
    trajectory: list[TrajectoryPoint]


@router.post("/simulate", response_model=SimulationResult)
async def simulate_portfolio(
    request: SimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> SimulationResult:
    """
    Run portfolio simulation.
    
    Args:
        request: Simulation parameters
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Simulation results
    """
    from app.models.stock import Stock
    from sqlalchemy import select
    import math
    
    # Asset class fallbacks if stocks are not in DB
    DEFAULT_METRICS = {
        "AAPL": {"return": 0.12, "volatility": 0.22, "beta": 1.2, "max_dd": -0.25},
        "MSFT": {"return": 0.11, "volatility": 0.20, "beta": 1.1, "max_dd": -0.22},
        "NVDA": {"return": 0.18, "volatility": 0.35, "beta": 1.7, "max_dd": -0.38},
        "TSLA": {"return": 0.15, "volatility": 0.40, "beta": 1.5, "max_dd": -0.50},
        "GOOGL": {"return": 0.10, "volatility": 0.21, "beta": 1.1, "max_dd": -0.24},
        "AMZN": {"return": 0.11, "volatility": 0.24, "beta": 1.15, "max_dd": -0.28},
        "META": {"return": 0.13, "volatility": 0.28, "beta": 1.25, "max_dd": -0.32},
        "TLT": {"return": 0.04, "volatility": 0.08, "beta": 0.15, "max_dd": -0.12},
        "GLD": {"return": 0.06, "volatility": 0.12, "beta": 0.05, "max_dd": -0.15},
        "BIL": {"return": 0.025, "volatility": 0.01, "beta": 0.00, "max_dd": -0.01},
    }
    
    portfolio_return = 0.0
    portfolio_vol = 0.0
    portfolio_beta = 0.0
    portfolio_max_dd = 0.0
    
    for item in request.stocks:
        ticker_upper = item.ticker.upper()
        weight = item.weight
        
        stmt = select(Stock).where(Stock.ticker == ticker_upper)
        res = await db.execute(stmt)
        db_stock = res.scalar_one_or_none()
        
        if db_stock:
            stock_vol = (db_stock.risk_score or 50.0) / 200.0
            stock_beta = db_stock.beta or 1.0
            stock_return = 0.02 + (db_stock.research_score or 50.0) * 0.0015
            stock_max_dd = -stock_vol * 1.2
        else:
            m = DEFAULT_METRICS.get(ticker_upper, {"return": 0.08, "volatility": 0.15, "beta": 1.0, "max_dd": -0.15})
            stock_return = m["return"]
            stock_vol = m["volatility"]
            stock_beta = m["beta"]
            stock_max_dd = m["max_dd"]
            
        portfolio_return += weight * stock_return
        portfolio_vol += weight * stock_vol
        portfolio_beta += weight * stock_beta
        portfolio_max_dd = min(portfolio_max_dd, stock_max_dd)
        
    # Apply simple diversification benefit to volatility
    portfolio_vol = portfolio_vol * 0.95
    
    rf = 0.025  # Risk-free rate
    sharpe = (portfolio_return - rf) / portfolio_vol if portfolio_vol > 0 else 0.0
    risk_adjusted = portfolio_return - (0.5 * portfolio_vol)
    
    # Calculate monthly projection trajectory
    trajectory = []
    current_val = request.initial_investment
    monthly_ret = portfolio_return / 12.0
    monthly_vol = portfolio_vol / (12.0 ** 0.5)
    
    for month in range(0, request.time_horizon_months + 1):
        median_val = current_val * ((1.0 + monthly_ret) ** month)
        upper_val = median_val * math.exp(1.645 * monthly_vol * (month ** 0.5))
        lower_val = median_val * math.exp(-1.645 * monthly_vol * (month ** 0.5))
        
        trajectory.append(
            TrajectoryPoint(
                month=month,
                median=round(median_val, 2),
                upper_95=round(upper_val, 2),
                lower_5=round(lower_val, 2)
            )
        )
        
    return SimulationResult(
        expected_return=round(portfolio_return * 100, 2),
        expected_volatility=round(portfolio_vol * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown=round(portfolio_max_dd * 100, 2),
        risk_adjusted_return=round(risk_adjusted * 100, 2),
        trajectory=trajectory
    )
