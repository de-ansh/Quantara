"""Portfolio simulation and management API endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.core.dependencies import CurrentUser, DBSession
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.stock import Stock
from app.services.portfolio_analytics import PortfolioAnalyticsEngine

router = APIRouter()


class PositionBase(BaseModel):
    """Position request schema."""

    ticker: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight (0.0 - 1.0)")
    shares: float = Field(0.0, ge=0)
    cost_basis: float = Field(0.0, ge=0)


class PositionResponse(PositionBase):
    """Position response schema."""

    id: int
    portfolio_id: int


class PortfolioCreate(BaseModel):
    """Portfolio creation request schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    initial_investment: float = Field(100000.0, gt=0)
    positions: list[PositionBase] = []


class PortfolioUpdate(BaseModel):
    """Portfolio update request schema."""

    name: str | None = None
    description: str | None = None
    initial_investment: float | None = Field(None, gt=0)
    positions: list[PositionBase] | None = None


class PortfolioResponse(BaseModel):
    """Portfolio response schema."""

    id: int
    user_id: int
    name: str
    description: str | None
    initial_investment: float
    positions: list[PositionResponse]
    created_at: datetime
    updated_at: datetime


class PortfoliosListResponse(BaseModel):
    """List of portfolios response schema."""

    portfolios: list[PortfolioResponse]
    total_count: int


@router.get("/", response_model=PortfoliosListResponse)
async def list_portfolios(
    current_user: CurrentUser,
    db: DBSession,
) -> PortfoliosListResponse:
    """List all portfolios for current user."""
    user_id = int(current_user["id"])
    stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .order_by(desc(Portfolio.updated_at))
    )
    result = await db.execute(stmt)
    portfolios = result.scalars().all()

    items = [
        PortfolioResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            description=p.description,
            initial_investment=p.initial_investment,
            positions=[
                PositionResponse(
                    id=pos.id,
                    portfolio_id=pos.portfolio_id,
                    ticker=pos.ticker,
                    weight=pos.weight,
                    shares=pos.shares,
                    cost_basis=pos.cost_basis,
                )
                for pos in p.positions
            ],
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in portfolios
    ]

    return PortfoliosListResponse(portfolios=items, total_count=len(items))


@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    request: PortfolioCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> PortfolioResponse:
    """Create a new portfolio with initial positions."""
    user_id = int(current_user["id"])
    now = datetime.utcnow()
    new_portfolio = Portfolio(
        user_id=user_id,
        name=request.name,
        description=request.description,
        initial_investment=request.initial_investment,
        created_at=now,
        updated_at=now,
    )
    db.add(new_portfolio)
    await db.flush()

    for pos in request.positions:
        ticker_upper = pos.ticker.upper()
        # Verify or auto-seed stock dependency for FK integrity
        stock_check = await db.execute(select(Stock).where(Stock.ticker == ticker_upper))
        if not stock_check.scalar_one_or_none():
            db.add(Stock(ticker=ticker_upper, name=ticker_upper))
            await db.flush()

        p_pos = PortfolioPosition(
            portfolio=new_portfolio,
            portfolio_id=new_portfolio.id or 0,
            ticker=ticker_upper,
            weight=pos.weight,
            shares=pos.shares,
            cost_basis=pos.cost_basis,
        )
        db.add(p_pos)

    await db.commit()
    await db.refresh(new_portfolio)

    return PortfolioResponse(
        id=new_portfolio.id or 1,
        user_id=new_portfolio.user_id,
        name=new_portfolio.name,
        description=new_portfolio.description,
        initial_investment=new_portfolio.initial_investment,
        positions=[
            PositionResponse(
                id=pos.id or 0,
                portfolio_id=pos.portfolio_id or new_portfolio.id or 1,
                ticker=pos.ticker,
                weight=pos.weight,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
            )
            for pos in new_portfolio.positions
        ],
        created_at=new_portfolio.created_at or now,
        updated_at=new_portfolio.updated_at or now,
    )


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> PortfolioResponse:
    """Get portfolio by ID."""
    user_id = int(current_user["id"])
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    return PortfolioResponse(
        id=portfolio.id,
        user_id=portfolio.user_id,
        name=portfolio.name,
        description=portfolio.description,
        initial_investment=portfolio.initial_investment,
        positions=[
            PositionResponse(
                id=pos.id,
                portfolio_id=pos.portfolio_id,
                ticker=pos.ticker,
                weight=pos.weight,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
            )
            for pos in portfolio.positions
        ],
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
    )


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    request: PortfolioUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> PortfolioResponse:
    """Update portfolio metadata or rebalance positions."""
    user_id = int(current_user["id"])
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    if request.name is not None:
        portfolio.name = request.name
    if request.description is not None:
        portfolio.description = request.description
    if request.initial_investment is not None:
        portfolio.initial_investment = request.initial_investment

    if request.positions is not None:
        # Remove previous positions
        del_stmt = select(PortfolioPosition).where(PortfolioPosition.portfolio_id == portfolio.id)
        existing = (await db.execute(del_stmt)).scalars().all()
        for ep in existing:
            await db.delete(ep)
        portfolio.positions.clear()
        await db.flush()

        # Add new positions
        for pos in request.positions:
            ticker_upper = pos.ticker.upper()
            stock_check = await db.execute(select(Stock).where(Stock.ticker == ticker_upper))
            if not stock_check.scalar_one_or_none():
                db.add(Stock(ticker=ticker_upper, name=ticker_upper))
                await db.flush()

            p_pos = PortfolioPosition(
                portfolio=portfolio,
                portfolio_id=portfolio.id,
                ticker=ticker_upper,
                weight=pos.weight,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
            )
            db.add(p_pos)

    portfolio.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(portfolio)

    return PortfolioResponse(
        id=portfolio.id,
        user_id=portfolio.user_id,
        name=portfolio.name,
        description=portfolio.description,
        initial_investment=portfolio.initial_investment,
        positions=[
            PositionResponse(
                id=pos.id or 0,
                portfolio_id=pos.portfolio_id or portfolio.id,
                ticker=pos.ticker,
                weight=pos.weight,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
            )
            for pos in portfolio.positions
        ],
        created_at=portfolio.created_at or datetime.utcnow(),
        updated_at=portfolio.updated_at or datetime.utcnow(),
    )


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete portfolio by ID."""
    user_id = int(current_user["id"])
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    result = await db.execute(stmt)
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    await db.delete(portfolio)
    await db.commit()
    return None


class PortfolioStock(BaseModel):
    """Portfolio stock schema."""

    ticker: str
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight (0-1)")


class SimulationRequest(BaseModel):
    """Portfolio simulation request schema."""

    stocks: list[PortfolioStock]
    initial_investment: float = Field(..., gt=0)
    time_horizon_months: int = Field(..., ge=1, le=360)
    volatility_mode: str = Field(
        "base", description="Volatility assumption: 'conservative', 'base', or 'aggressive'"
    )


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
    diversification_benefit_pct: float = Field(
        0.0, description="Volatility reduction achieved through diversification (%)"
    )
    asset_volatilities: dict[str, float] = Field(
        default_factory=dict, description="Individual asset annualized volatilities"
    )
    correlation_matrix: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Pairwise asset correlation matrix"
    )
    covariance_matrix: list[list[float]] = Field(
        default_factory=list, description="Asset covariance matrix (w^T * Sigma * w)"
    )


@router.post("/simulate", response_model=SimulationResult)
async def simulate_portfolio(
    request: SimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> SimulationResult:
    """
    Run portfolio simulation using Markowitz Modern Portfolio Theory covariance.

    Args:
        request: Simulation parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        Simulation results with MPT covariance metrics and trajectories
    """
    import math

    from sqlalchemy import select

    from app.models.stock import Stock

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

    tickers: list[str] = []
    weights: list[float] = []
    vols: list[float] = []
    returns: list[float] = []
    sectors: dict[str, str | None] = {}
    portfolio_beta = 0.0
    portfolio_max_dd = 0.0

    for item in request.stocks:
        ticker_upper = item.ticker.upper()
        tickers.append(ticker_upper)
        weights.append(item.weight)

        stmt = select(Stock).where(Stock.ticker == ticker_upper)
        res = await db.execute(stmt)
        db_stock = res.scalar_one_or_none()

        if db_stock:
            stock_vol = (db_stock.risk_score or 50.0) / 200.0
            stock_beta = db_stock.beta or 1.0
            stock_return = 0.02 + (db_stock.research_score or 50.0) * 0.0015
            stock_max_dd = -stock_vol * 1.2
            sectors[ticker_upper] = db_stock.sector
        else:
            m = DEFAULT_METRICS.get(
                ticker_upper, {"return": 0.08, "volatility": 0.15, "beta": 1.0, "max_dd": -0.15}
            )
            stock_return = m["return"]
            stock_vol = m["volatility"]
            stock_beta = m["beta"]
            stock_max_dd = m["max_dd"]
            sectors[ticker_upper] = None

        returns.append(stock_return)
        vols.append(stock_vol)
        portfolio_beta += item.weight * stock_beta
        portfolio_max_dd = min(portfolio_max_dd, stock_max_dd)

    # Calculate MPT Covariance Matrix & Portfolio Risk
    analytics = PortfolioAnalyticsEngine.calculate_portfolio_metrics(
        tickers=tickers,
        weights=weights,
        volatilities=vols,
        expected_returns=returns,
        sectors=sectors,
    )

    portfolio_return = analytics.portfolio_return
    portfolio_vol = analytics.portfolio_volatility

    # Scale metrics based on user's scenario assumption
    vol_mode = (request.volatility_mode or "base").lower()
    if vol_mode == "conservative":
        portfolio_vol *= 1.20
        portfolio_return *= 0.90
        portfolio_max_dd *= 1.25
    elif vol_mode == "aggressive":
        portfolio_vol *= 0.85
        portfolio_return *= 1.10
        portfolio_max_dd *= 0.85

    rf = 0.025  # Risk-free rate
    sharpe = (portfolio_return - rf) / portfolio_vol if portfolio_vol > 0 else 0.0
    risk_adjusted = portfolio_return - (0.5 * portfolio_vol)

    # Calculate monthly projection trajectory
    trajectory = []
    current_val = request.initial_investment
    monthly_ret = portfolio_return / 12.0
    monthly_vol = portfolio_vol / (12.0**0.5)

    for month in range(0, request.time_horizon_months + 1):
        median_val = current_val * ((1.0 + monthly_ret) ** month)
        upper_val = median_val * math.exp(1.645 * monthly_vol * (month**0.5))
        lower_val = median_val * math.exp(-1.645 * monthly_vol * (month**0.5))

        trajectory.append(
            TrajectoryPoint(
                month=month,
                median=round(median_val, 2),
                upper_95=round(upper_val, 2),
                lower_5=round(lower_val, 2),
            )
        )

    return SimulationResult(
        expected_return=round(portfolio_return * 100, 2),
        expected_volatility=round(portfolio_vol * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown=round(portfolio_max_dd * 100, 2),
        risk_adjusted_return=round(risk_adjusted * 100, 2),
        trajectory=trajectory,
        diversification_benefit_pct=analytics.diversification_benefit_pct,
        asset_volatilities=analytics.asset_volatilities,
        correlation_matrix=analytics.correlation_matrix,
        covariance_matrix=analytics.covariance_matrix,
    )
