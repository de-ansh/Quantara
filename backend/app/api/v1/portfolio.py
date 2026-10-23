"""Portfolio simulation and management API endpoints."""

from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.core.dependencies import CurrentUser, DBSession
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.stock import Stock
from app.services.portfolio_analytics import PortfolioAnalyticsEngine
from app.services.stock_lookup import get_or_track_stock

router = APIRouter()


class PositionBase(BaseModel):
    """Position request schema."""

    ticker: str = Field(..., pattern=r"^[A-Za-z0-9.\-^]{1,20}$")
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


async def _verify_positions(db: DBSession, positions: list[PositionBase]) -> None:
    """Reject duplicate or unknown tickers before anything is written."""
    tickers = [p.ticker.upper() for p in positions]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Each ticker can appear only once in a portfolio",
        )
    unknown = [t for t in tickers if await get_or_track_stock(db, t) is None]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No market data found for: {', '.join(unknown)}",
        )


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
    await _verify_positions(db, request.positions)
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
        await _verify_positions(db, request.positions)

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

    stocks: list[PortfolioStock] = Field(..., min_length=1)
    initial_investment: float = Field(..., gt=0)
    time_horizon_months: int = Field(..., ge=1, le=360)
    volatility_mode: str = Field(
        "base", description="Volatility assumption: 'conservative', 'base', or 'aggressive'"
    )


class TrajectoryPoint(BaseModel):
    """Projected portfolio value percentiles (lognormal model) at a given month."""

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
    portfolio_beta: float = Field(0.0, description="Weighted beta vs S&P 500 / NIFTY 50")
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
    estimated_tickers: list[str] = Field(
        default_factory=list,
        description="Tickers lacking price history, simulated with default asset-class estimates",
    )


@router.post("/simulate", response_model=SimulationResult)
async def simulate_portfolio(
    request: SimulationRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> SimulationResult:
    """
    Run portfolio simulation using Markowitz Modern Portfolio Theory covariance.

    Volatility, correlation, beta and drawdown come from one year of daily returns;
    expected return is CAPM (risk-free + beta * equity premium). Tickers without enough
    history fall back to asset-class defaults and are listed in `estimated_tickers`.

    Args:
        request: Simulation parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        Simulation results with MPT covariance metrics and trajectories
    """
    import math

    from app.api.v1.risk import MIN_OVERLAP_DAYS, _get_daily_returns

    total_weight = sum(item.weight for item in request.stocks)
    if abs(total_weight - 1.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Portfolio weights must sum to 1.0 (got {total_weight:.3f})",
        )

    rf = 0.025  # Risk-free rate
    equity_premium = 0.055  # Long-run equity risk premium for CAPM

    # Fallbacks for tickers without price history
    DEFAULT_METRICS = {
        "TLT": {"volatility": 0.08, "beta": 0.15, "max_dd": -0.12},
        "GLD": {"volatility": 0.12, "beta": 0.05, "max_dd": -0.15},
        "BIL": {"volatility": 0.01, "beta": 0.00, "max_dd": -0.01},
    }
    GENERIC_EQUITY = {"volatility": 0.25, "beta": 1.0, "max_dd": -0.30}

    tickers = [item.ticker.upper() for item in request.stocks]
    weights = [item.weight for item in request.stocks]
    benchmarks = {t: "^NSEI" if t.endswith((".NS", ".BO")) else "^GSPC" for t in tickers}
    daily = await _get_daily_returns(tuple(dict.fromkeys(tickers + list(benchmarks.values()))))

    def _history(t: str) -> "pd.Series | None":
        if daily is None or t not in daily:
            return None
        series = daily[t].dropna()
        return series if len(series) >= MIN_OVERLAP_DAYS else None

    db_rows = (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))).scalars().all()
    db_stocks = {row.ticker: row for row in db_rows}

    vols: list[float] = []
    returns: list[float] = []
    sectors: dict[str, str | None] = {}
    estimated: list[str] = []
    portfolio_beta = 0.0
    asset_max_dd = 0.0

    for t, w in zip(tickers, weights, strict=True):
        db_stock = db_stocks.get(t)
        sectors[t] = db_stock.sector if db_stock else None
        hist, bench = _history(t), _history(benchmarks[t])

        if hist is not None:
            vol = float(hist.std() * math.sqrt(252))
            growth = (1 + hist).cumprod()
            max_dd = float((growth / growth.cummax() - 1).min())
            pair = pd.concat([hist, bench], axis=1).dropna() if bench is not None else None
            if pair is not None and len(pair) >= MIN_OVERLAP_DAYS and pair.iloc[:, 1].var() > 0:
                beta = float(pair.iloc[:, 0].cov(pair.iloc[:, 1]) / pair.iloc[:, 1].var())
            else:
                beta = db_stock.beta if db_stock and db_stock.beta is not None else 1.0
        else:
            estimated.append(t)
            m = DEFAULT_METRICS.get(t, GENERIC_EQUITY)
            vol, max_dd = m["volatility"], m["max_dd"]
            beta = db_stock.beta if db_stock and db_stock.beta is not None else m["beta"]

        vols.append(vol)
        returns.append(rf + beta * equity_premium)
        portfolio_beta += w * beta
        asset_max_dd = min(asset_max_dd, max_dd)

    # Real pairwise correlations override the asset-class estimates where history overlaps
    custom_corr = PortfolioAnalyticsEngine.build_correlation_matrix(tickers, sectors)
    for a in tickers:
        for b in tickers:
            ha, hb = _history(a), _history(b)
            if a == b or ha is None or hb is None:
                continue
            pair = pd.concat([ha, hb], axis=1).dropna()
            if len(pair) >= MIN_OVERLAP_DAYS:
                corr = pair.iloc[:, 0].corr(pair.iloc[:, 1])
                if not pd.isna(corr):
                    custom_corr[a][b] = round(float(corr), 4)

    # Portfolio drawdown from the weighted daily series when every asset has history
    if not estimated:
        portfolio_daily = (
            pd.concat([_history(t) for t in tickers], axis=1).dropna() * weights
        ).sum(axis=1)
        growth = (1 + portfolio_daily).cumprod()
        portfolio_max_dd = float((growth / growth.cummax() - 1).min())
    else:
        portfolio_max_dd = asset_max_dd

    # Calculate MPT Covariance Matrix & Portfolio Risk
    analytics = PortfolioAnalyticsEngine.calculate_portfolio_metrics(
        tickers=tickers,
        weights=weights,
        volatilities=vols,
        expected_returns=returns,
        sectors=sectors,
        custom_correlations=custom_corr,
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

    sharpe = (portfolio_return - rf) / portfolio_vol if portfolio_vol > 0 else 0.0
    risk_adjusted = portfolio_return - (0.5 * portfolio_vol)

    # Lognormal (GBM) percentiles: median grows at the log drift mu - sigma^2 / 2
    trajectory = []
    current_val = request.initial_investment
    log_drift = math.log1p(portfolio_return) - 0.5 * portfolio_vol**2

    for month in range(0, request.time_horizon_months + 1):
        years = month / 12.0
        median_val = current_val * math.exp(log_drift * years)
        upper_val = median_val * math.exp(1.645 * portfolio_vol * math.sqrt(years))
        lower_val = median_val * math.exp(-1.645 * portfolio_vol * math.sqrt(years))

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
        portfolio_beta=round(portfolio_beta, 2),
        trajectory=trajectory,
        diversification_benefit_pct=analytics.diversification_benefit_pct,
        asset_volatilities=analytics.asset_volatilities,
        correlation_matrix=analytics.correlation_matrix,
        covariance_matrix=analytics.covariance_matrix,
        estimated_tickers=estimated,
    )
