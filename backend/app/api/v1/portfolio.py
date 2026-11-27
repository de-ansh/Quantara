"""Portfolio simulation and management API endpoints."""

from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, desc, select

from app.api.v1.tax import TradeIn
from app.core.clock import utcnow
from app.core.dependencies import CurrentUser, DBSession
from app.core.logging import get_logger
from app.models.listed_security import ListedSecurity
from app.models.mutual_fund import FundHolding, MutualFund
from app.models.portfolio import Portfolio, PortfolioFund, PortfolioPosition, PortfolioTrade
from app.models.stock import Stock
from app.models.user import User
from app.services.mutual_funds import match_funds
from app.services.portfolio_analytics import PortfolioAnalyticsEngine
from app.services.portfolio_balance import (
    FundLine,
    Look,
    Target,
    balance_flags,
    exposures,
    rebalance_plan,
)
from app.services.stock_lookup import get_or_track_stock
from app.services.tax_harvest import LTCG_EXEMPTION, Book, Lot, build_book, tax_on, xirr
from app.services.tax_harvest import Trade as TaxTrade

router = APIRouter()
logger = get_logger(__name__)


class PositionBase(BaseModel):
    """Position request schema."""

    ticker: str = Field(..., pattern=r"^[A-Za-z0-9&.\-^]{1,20}$")  # & for M&M.NS, J&KBANK.NS
    weight: float = Field(
        0.0, ge=0, le=1, description="Portfolio weight (0.0 - 1.0); derived from shares when all are 0"
    )
    shares: float = Field(0.0, ge=0)
    cost_basis: float = Field(0.0, ge=0, description="Average cost per share")


class PositionResponse(PositionBase):
    """Position response schema."""

    id: int
    portfolio_id: int


class FundPositionBase(BaseModel):
    """Units of one AMFI mutual fund scheme."""

    scheme_code: int = Field(..., gt=0)
    units: float = Field(..., gt=0)
    cost_basis: float = Field(0.0, ge=0, description="Average cost per unit")


class FundPositionResponse(FundPositionBase):
    """A fund holding with its scheme name."""

    name: str


class PortfolioCreate(BaseModel):
    """Portfolio creation request schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    initial_investment: float = Field(100000.0, gt=0)
    positions: list[PositionBase] = []
    funds: list[FundPositionBase] = []


class PortfolioUpdate(BaseModel):
    """Portfolio update request schema."""

    name: str | None = None
    description: str | None = None
    initial_investment: float | None = Field(None, gt=0)
    positions: list[PositionBase] | None = None
    funds: list[FundPositionBase] | None = None


class PortfolioResponse(BaseModel):
    """Portfolio response schema."""

    id: int
    user_id: int
    name: str
    description: str | None
    initial_investment: float
    positions: list[PositionResponse]
    funds: list[FundPositionResponse] = []
    created_at: datetime
    updated_at: datetime


def _funds_out(portfolio: Portfolio) -> list[FundPositionResponse]:
    return [
        FundPositionResponse(scheme_code=f.scheme_code, units=f.units, cost_basis=f.cost_basis, name=f.fund.name)
        for f in portfolio.funds
    ]


async def _verify_funds(db: DBSession, funds: list[FundPositionBase]) -> None:
    """Reject a scheme listed twice or one AMFI doesn't have."""
    if not funds:
        return
    codes = [f.scheme_code for f in funds]
    if len(set(codes)) != len(codes):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Each mutual fund can appear only once in a portfolio",
        )
    known = set((await db.execute(select(MutualFund.scheme_code).where(MutualFund.scheme_code.in_(codes)))).scalars())
    if unknown := [str(c) for c in codes if c not in known]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown mutual fund scheme: {', '.join(unknown)}",
        )


def _is_indian(ticker: str) -> bool:
    return ticker.upper().endswith((".NS", ".BO"))


async def _verify_positions(db: DBSession, positions: list[PositionBase]) -> None:
    """Reject duplicate or unknown tickers before anything is written.

    When no weights are given but every position has shares, weights are set from market value.
    """
    tickers = [p.ticker.upper() for p in positions]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Each ticker can appear only once in a portfolio",
        )
    stocks = {t: await get_or_track_stock(db, t) for t in tickers}
    unknown = [t for t, s in stocks.items() if s is None]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No market data found for: {', '.join(unknown)}",
        )
    # Store the listing each typed ticker resolved to ("ITC" -> ITC.NS), then re-check for doubles
    found = {t: s for t, s in stocks.items() if s is not None}  # every one, after the check above
    for p in positions:
        p.ticker = found[p.ticker.upper()].ticker
    tickers = [p.ticker for p in positions]
    if len(set(tickers)) != len(tickers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Each ticker can appear only once in a portfolio",
        )
    known = {s.ticker: s for s in found.values()}

    if positions and all(p.weight == 0 for p in positions):
        if not all(p.shares > 0 for p in positions):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Give each holding either a weight or a share count",
            )
        if len({_is_indian(t) for t in tickers}) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Mixed USD/INR portfolios need explicit weights",
            )
        values = [p.shares * (known[p.ticker.upper()].price or 0.0) for p in positions]
        total = sum(values)
        if total <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No current prices to derive weights from; enter weights instead",
            )
        for p, v in zip(positions, values, strict=True):
            p.weight = v / total


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
            funds=_funds_out(p),
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
    await _verify_funds(db, request.funds)
    now = utcnow()
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
    for fund in request.funds:
        db.add(PortfolioFund(portfolio_id=new_portfolio.id, **fund.model_dump()))

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
        funds=_funds_out(new_portfolio),
        created_at=new_portfolio.created_at or now,
        updated_at=new_portfolio.updated_at or now,
    )


class HoldingPerformance(BaseModel):
    """Live valuation of one position (amounts in the listing currency)."""

    kind: str = Field("stock", description="stock, or fund (ticker is then the AMFI scheme code, price the NAV)")
    ticker: str
    name: str
    sector: str | None
    currency: str
    shares: float
    avg_cost: float
    price: float | None
    market_value: float | None
    cost_value: float
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    day_change: float | None
    weight_by_value: float | None = Field(None, description="Share of its currency's market value")
    price_date: date | None = Field(None, description="Funds: the day of the NAV used (AMFI publishes one a day)")


class CurrencyTotals(BaseModel):
    """Portfolio totals for holdings in one currency (USD and INR are never summed)."""

    currency: str
    market_value: float
    cost_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float | None
    day_change: float
    sector_allocation: dict[str, float] = Field(
        default_factory=dict, description="Sector -> % of this currency's market value"
    )


class PortfolioPerformance(BaseModel):
    """Holdings valuation and P&L for a portfolio."""

    portfolio_id: int
    holdings: list[HoldingPerformance]
    totals: list[CurrencyTotals]
    prices_as_of: datetime | None = Field(None, description="Oldest price timestamp used")
    weight_only_tickers: list[str] = Field(
        default_factory=list, description="Positions without a share count (not valued)"
    )


PRICE_MAX_AGE = timedelta(minutes=15)


class HoldingUpdateOut(BaseModel):
    """Something that happened to (or is due for) a holding."""

    kind: str = Field(..., description="signal, alert, transcript, results, verdict or event")
    day: date
    text: str
    tone: str = Field("neutral", description="good, bad or neutral")
    upcoming: bool = False


class PortfolioUpdates(BaseModel):
    """One portfolio's live valuation, plus updates per holding ticker."""

    portfolio_id: int
    name: str
    performance: PortfolioPerformance
    updates: dict[str, list[HoldingUpdateOut]]


class PortfolioUpdatesResponse(BaseModel):
    portfolios: list[PortfolioUpdates]


class TargetMix(BaseModel):
    """Asset mix to rebalance towards (% of value, summing to 100) and the concentration limits."""

    equity: float = Field(..., ge=0, le=100)
    debt: float = Field(..., ge=0, le=100)
    cash: float = Field(..., ge=0, le=100)
    gold: float = Field(..., ge=0, le=100)
    max_stock: float = Field(20, ge=5, le=100, description="one company, % of the portfolio")
    max_sector: float = Field(35, ge=10, le=100, description="one sector, % of the portfolio")
    is_default: bool = Field(False, description="true: not saved yet, the risk profile's starting point")

    @model_validator(mode="after")
    def _sums_to_100(self) -> "TargetMix":
        if abs(self.equity + self.debt + self.cash + self.gold - 100) > 0.01:
            raise ValueError("Equity, debt, cash and gold must add up to 100%")
        return self


async def _target(db: DBSession, user_id: int, risk_level: str | None) -> Target:
    user = await db.get(User, user_id)
    return Target.load(user.target_mix if user else None, risk_level)


@router.get("/target-mix", response_model=TargetMix)
async def get_target_mix(current_user: CurrentUser, db: DBSession) -> TargetMix:
    """The user's target mix, or their risk profile's starting point until they save one."""
    return TargetMix(**vars(await _target(db, int(current_user["id"]), current_user.get("risk_level"))))


@router.put("/target-mix", response_model=TargetMix)
async def save_target_mix(body: TargetMix, current_user: CurrentUser, db: DBSession) -> TargetMix:
    user = await db.get(User, int(current_user["id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.target_mix = body.model_dump(exclude={"is_default"})
    await db.commit()
    return body.model_copy(update={"is_default": False})


@router.delete("/target-mix", response_model=TargetMix)
async def reset_target_mix(current_user: CurrentUser, db: DBSession) -> TargetMix:
    """Back to the risk profile's starting point."""
    user = await db.get(User, int(current_user["id"]))
    if user is not None:
        user.target_mix = None
        await db.commit()
    return TargetMix(**vars(await _target(db, int(current_user["id"]), current_user.get("risk_level"))))


class BalanceFlagOut(BaseModel):
    kind: str = Field(..., description="stock, sector, mix, verdict or elsewhere")
    title: str
    detail: str
    currency: str
    ticker: str | None = None
    amount: float | None = None


class TradeOut(BaseModel):
    action: str = Field(..., description="sell or add")
    asset_class: str
    amount: float
    currency: str
    ticker: str | None = None
    name: str | None = None
    reason: str
    gain: float | None = Field(None, description="profit (negative: loss) the sale realises, before tax")
    short_term_gain: float | None = Field(None, description="from tradebook buy dates; null without one")
    long_term_gain: float | None = None
    wait_until: date | None = Field(None, description="part of it turns long-term by then: waiting cuts the tax")
    held_in: list[str] = Field(default_factory=list, description="all-portfolios view: the portfolios holding it")


class ExposureOut(BaseModel):
    name: str
    ticker: str | None
    direct: float
    via_funds: float
    funds: list[str]
    pct: float = Field(..., description="% of the rupee holdings")


class PortfolioBalance(BaseModel):
    portfolio_id: int | None = Field(..., description="null: all the user's portfolios together")
    flags: list[BalanceFlagOut]
    mix: dict[str, dict[str, float]]  # currency -> asset class (equity, debt, cash, gold) -> % of value
    target: TargetMix
    plan: list[TradeOut]  # rupee holdings only
    plan_tax: float | None = Field(None, description="extra tax this financial year if every sale is made; "
                                   "null unless the tradebook covers every holding sold")
    exemption_left: float | None = Field(None, description="long-term gains still tax-free this financial year")
    exposures: list[ExposureOut] = Field(default_factory=list, description="biggest companies, direct plus through funds (rupees)")
    funds_looked_through: list[str] = Field(default_factory=list, description="funds whose holdings are counted")
    funds_not_looked_through: list[str] = Field(default_factory=list, description="held funds with no holdings yet")
    holdings_as_of: date | None = Field(None, description="oldest fund portfolio date among those counted")
    risk_level: str | None


TOP_EXPOSURES = 10
NewMoney = Query(0, ge=0, le=1e10, description="Rupees about to be added, invested before anything is sold")


@router.get("/{portfolio_id}/balance", response_model=PortfolioBalance)
async def get_portfolio_balance(
    portfolio_id: int, current_user: CurrentUser, db: DBSession, new_money: float = NewMoney,
) -> PortfolioBalance:
    """Flags against the target mix, and the sells and adds that get back to it."""
    portfolios = (await db.execute(select(Portfolio).where(Portfolio.user_id == int(current_user["id"])))).scalars().all()
    portfolio = next((p for p in portfolios if p.id == portfolio_id), None)
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    perf = await _valuation(db, portfolio)
    held = {h.ticker for h in perf.holdings if h.kind == "stock"}
    elsewhere: dict[str, list[str]] = {}
    for other in portfolios:
        if other.id != portfolio_id:
            for pos in other.positions:
                if pos.shares > 0 and pos.ticker in held:
                    elsewhere.setdefault(pos.ticker, []).append(other.name)
    return await _balance(db, current_user, portfolio_id, perf.holdings, elsewhere, {}, new_money,
                          [b] if (b := await _book(db, portfolio)) else [])


@router.get("/balance", response_model=PortfolioBalance)
async def get_all_balance(current_user: CurrentUser, db: DBSession, new_money: float = NewMoney) -> PortfolioBalance:
    """Every portfolio as one: a stock held in several counts once, at its combined size."""
    portfolios = (await db.execute(select(Portfolio).where(Portfolio.user_id == int(current_user["id"])))).scalars().all()
    merged: dict[tuple[str, str], HoldingPerformance] = {}
    held_in: dict[str, list[str]] = {}
    books = [b for p in portfolios if (b := await _book(db, p))]
    for portfolio in portfolios:
        for h in (await _valuation(db, portfolio)).holdings:
            held_in.setdefault(h.ticker, []).append(portfolio.name)
            key = (h.kind, h.ticker)
            if key not in merged:
                merged[key] = h.model_copy()
                continue
            m = merged[key]
            m.shares += h.shares
            m.cost_value += h.cost_value
            if h.market_value is not None:
                m.market_value = (m.market_value or 0) + h.market_value
            if h.unrealized_pnl is not None:
                m.unrealized_pnl = (m.unrealized_pnl or 0) + h.unrealized_pnl
    return await _balance(db, current_user, None, list(merged.values()), {}, held_in, new_money, books)


class FundStake(BaseModel):
    name: str
    amount: float = Field(..., description="rupees of the company held through this fund")
    weight: float = Field(..., description="% of the fund in the company")


class StockExposure(BaseModel):
    ticker: str
    via_funds: float
    funds: list[FundStake]
    holdings_as_of: date | None = Field(None, description="oldest fund portfolio date among those counted")


@router.get("/exposure/{ticker}", response_model=StockExposure)
async def get_stock_exposure(ticker: str, current_user: CurrentUser, db: DBSession) -> StockExposure:
    """How much of one company you own through your funds, across all portfolios."""
    symbol = ticker.upper().split(".")[0]  # funds list the NSE ticker; the page may show the BSE one
    value: dict[str, float] = {}
    names: dict[str, str] = {}
    portfolios = (await db.execute(select(Portfolio).where(Portfolio.user_id == int(current_user["id"])))).scalars().all()
    for portfolio in portfolios:
        for h in (await _valuation(db, portfolio)).holdings:
            if h.kind == "fund" and h.market_value:
                value[h.ticker] = value.get(h.ticker, 0.0) + h.market_value
                names[h.ticker] = h.name
    look, as_of = await _look(db, [int(code) for code in value])
    stakes = []
    for code, lines in look.items():
        weights = sum(line.weight for line in lines)  # as exposures(): a fund's lines scaled to 100%
        weight = sum(line.weight for line in lines
                     if line.kind == "equity" and line.ticker and line.ticker.split(".")[0] == symbol)
        if weight and weights > 0:
            stakes.append(FundStake(name=names[code], amount=round(value[code] * weight / weights, 2), weight=round(weight, 2)))
    stakes.sort(key=lambda s: -s.amount)
    return StockExposure(ticker=ticker.upper(), via_funds=round(sum(s.amount for s in stakes), 2), funds=stakes,
                         holdings_as_of=min(as_of) if stakes and as_of else None)


async def _look(db: DBSession, fund_codes: list[int]) -> tuple[Look, list[date]]:
    """What each fund owns, from its latest monthly portfolio, and those portfolios' dates."""
    look: Look = {}
    if not fund_codes:
        return look, []
    for row in (await db.execute(select(FundHolding).where(FundHolding.scheme_code.in_(fund_codes)))).scalars():
        look.setdefault(str(row.scheme_code), []).append(FundLine(row.name, row.ticker, row.kind, row.weight))
    as_of = [d for d in (await db.execute(select(MutualFund.holdings_as_of).where(
        MutualFund.scheme_code.in_(fund_codes)))).scalars() if d]
    return look, as_of


async def _balance(
    db: DBSession,
    current_user: dict,
    portfolio_id: int | None,
    holdings: list[HoldingPerformance],
    elsewhere: dict[str, list[str]],
    held_in: dict[str, list[str]],
    new_money: float,
    books: list[Book],
) -> PortfolioBalance:
    from app.services.verdict_tracking import verdict_for

    risk_level = current_user.get("risk_level")
    tolerance = current_user.get("volatility_tolerance")
    verdicts: dict[str, str] = {}
    if risk_level:
        held = [h.ticker for h in holdings if h.kind == "stock"]
        for stock in (await db.execute(select(Stock).where(Stock.ticker.in_(held)))).scalars():
            v = await verdict_for(db, stock, risk_level, float(tolerance) if tolerance is not None else None)
            if v:
                verdicts[stock.ticker] = v.verdict
    target = await _target(db, int(current_user["id"]), risk_level)
    # Look through funds: what each held fund owns, from its latest monthly portfolio
    look, as_of = await _look(db, [int(h.ticker) for h in holdings if h.kind == "fund"])
    funds = [h for h in holdings if h.kind == "fund"]
    flags, mix = balance_flags(holdings, verdicts, elsewhere, target,
                               "this portfolio" if portfolio_id else "all your portfolios", look)
    rupees = [h for h in holdings if h.currency == "INR" and h.market_value]
    rupee_total = sum(h.market_value or 0.0 for h in rupees)
    top = [
        ExposureOut(name=e.name, ticker=e.ticker, direct=round(e.direct, 2), via_funds=round(e.via_funds, 2),
                    funds=e.funds, pct=round(e.total / rupee_total * 100, 2))
        for e in exposures(rupees, look)[:TOP_EXPOSURES]
    ] if rupee_total else []
    lots: dict[str, list[Lot]] = {}
    for book in books:  # several portfolios: FIFO per demat account, approximated here as one queue per stock
        for lot in book.lots:
            lots.setdefault(lot.symbol, []).append(lot)
    plan = rebalance_plan(holdings, target, verdicts, new_money, lots=lots, look=look)
    sells = [t for t in plan if t.action == "sell"]
    plan_tax = exemption_left = None
    if books:
        st = sum(b.realized.short_term for b in books)
        lt = sum(b.realized.long_term for b in books)
        exemption_left = round(max(0.0, LTCG_EXEMPTION - max(0.0, lt + min(0.0, st))), 2)
        if sells and all(t.short_term_gain is not None for t in sells):
            st_plan = sum(t.short_term_gain or 0 for t in sells)
            lt_plan = sum(t.long_term_gain or 0 for t in sells)
            plan_tax = round(tax_on(st + st_plan, lt + lt_plan) - tax_on(st, lt), 2)
    return PortfolioBalance(
        portfolio_id=portfolio_id,
        flags=[BalanceFlagOut(**vars(f)) for f in flags],
        mix=mix,
        target=TargetMix(**vars(target)),
        plan=[TradeOut(**vars(t), held_in=held_in.get(t.ticker or "", [])) for t in plan],
        plan_tax=plan_tax,
        exemption_left=exemption_left,
        exposures=top,
        funds_looked_through=[h.name for h in funds if h.ticker in look],
        funds_not_looked_through=[h.name for h in funds if h.ticker not in look],
        holdings_as_of=min(as_of) if as_of else None,
        risk_level=risk_level,
    )


# --- Tradebook: the buy dates behind a portfolio's holdings -------------------------------------------------------


class TradebookImport(BaseModel):
    trades: list[TradeIn] = Field(..., min_length=1, max_length=50_000)


class TradebookGap(BaseModel):
    ticker: str
    portfolio_shares: float
    tradebook_shares: float


class TradebookSummary(BaseModel):
    imported_at: datetime
    trades: int
    first_trade: date | None
    excluded: list[str] = Field(..., description="symbols left out: a split or bonus the tradebook can't show")
    warnings: list[str]
    gaps: list[TradebookGap] = Field(..., description="holdings whose share count the tradebook doesn't explain")
    xirr: float | None = Field(None, description="annual return (%) on the tradebook's stocks, valued at today's prices")


async def _trades(db: DBSession, portfolio_id: int) -> list[TaxTrade]:
    rows = (await db.execute(
        select(PortfolioTrade).where(PortfolioTrade.portfolio_id == portfolio_id).order_by(PortfolioTrade.day)
    )).scalars().all()
    return [TaxTrade(r.symbol, r.day, r.side, r.quantity, r.price) for r in rows]


async def _book(db: DBSession, portfolio: Portfolio) -> Book | None:
    """Open lots and this year's realised gains from the stored tradebook; None when there isn't one."""
    if not portfolio.tradebook:
        return None
    excluded = set(portfolio.tradebook.get("excluded", []))
    trades = [t for t in await _trades(db, portfolio.id) if t.symbol not in excluded]
    return build_book(trades, date.today()) if trades else None


async def _summary(db: DBSession, portfolio: Portfolio) -> TradebookSummary | None:
    meta = portfolio.tradebook
    if not meta:
        return None
    excluded = set(meta.get("excluded", []))
    trades = [t for t in await _trades(db, portfolio.id) if t.symbol not in excluded]
    book = build_book(trades, date.today())
    open_shares: dict[str, float] = {}
    for lot in book.lots:
        open_shares[lot.symbol] = open_shares.get(lot.symbol, 0.0) + lot.quantity
    gaps = [
        TradebookGap(ticker=p.ticker, portfolio_shares=p.shares, tradebook_shares=round(open_shares.get(p.ticker, 0.0), 4))
        for p in portfolio.positions
        if p.shares > 0 and p.ticker not in excluded and abs(open_shares.get(p.ticker, 0.0) - p.shares) > max(0.01, p.shares * 0.01)
    ]
    # XIRR: money in on each buy, out on each sell, and what's still held, at today's price
    rows = (await db.execute(
        select(Stock.ticker, Stock.price).where(Stock.ticker.in_(list(open_shares)))
    )).all() if open_shares else []
    prices: dict[str, float] = {t: float(p) for t, p in rows if p}
    rate = None
    if all(prices.get(t) for t in open_shares):
        flows = [(t.day, (-1 if t.side == "buy" else 1) * t.quantity * t.price) for t in trades]
        flows.append((date.today(), sum(q * prices[t] for t, q in open_shares.items())))
        rate = xirr(flows)
    return TradebookSummary(
        imported_at=datetime.fromisoformat(meta["imported_at"]),
        trades=len(trades),
        first_trade=min((t.day for t in trades), default=None),
        excluded=sorted(excluded),
        warnings=meta.get("warnings", []),
        gaps=gaps,
        xirr=rate,
    )


async def _own(db: DBSession, current_user: dict, portfolio_id: int) -> Portfolio:
    portfolio = (await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == int(current_user["id"]))
    )).scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio


@router.put("/{portfolio_id}/trades", response_model=TradebookSummary)
async def import_tradebook(
    portfolio_id: int, body: TradebookImport, current_user: CurrentUser, db: DBSession
) -> TradebookSummary:
    """Replace the portfolio's tradebook. Splits and bonuses are checked once, here, since the lookup is slow."""
    from app.api.v1.tax import _all_split_dates
    from app.services.stock_lookup import resolve_ticker

    portfolio = await _own(db, current_user, portfolio_id)
    symbols = {t.symbol.upper() for t in body.trades}
    resolved = {s: await resolve_ticker(db, s) or s for s in symbols}
    trades = [TaxTrade(resolved[t.symbol.upper()], t.date, t.side, t.quantity, t.price) for t in body.trades]
    splits = await _all_split_dates({t.symbol for t in trades})
    book = build_book(trades, date.today(), {s: d for s, d in splits.items() if d})
    excluded = book.excluded
    unchecked = sorted(s for s, d in splits.items() if d is None)
    warnings = book.warnings + (
        [f"Couldn't check for bonuses or splits on {', '.join(unchecked)}; verify those with your broker"] if unchecked else []
    )

    await db.execute(delete(PortfolioTrade).where(PortfolioTrade.portfolio_id == portfolio_id))
    db.add_all(PortfolioTrade(portfolio_id=portfolio_id, symbol=t.symbol, day=t.day, side=t.side,
                              quantity=t.quantity, price=t.price) for t in trades)
    portfolio.tradebook = {"imported_at": utcnow().isoformat(), "excluded": excluded, "warnings": warnings}
    await db.commit()
    await db.refresh(portfolio)
    summary = await _summary(db, portfolio)
    assert summary is not None
    return summary


@router.get("/{portfolio_id}/trades", response_model=TradebookSummary | None)
async def get_tradebook(portfolio_id: int, current_user: CurrentUser, db: DBSession) -> TradebookSummary | None:
    """What the imported tradebook covers, its gaps and XIRR; null before one is imported."""
    return await _summary(db, await _own(db, current_user, portfolio_id))


@router.delete("/{portfolio_id}/trades", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tradebook(portfolio_id: int, current_user: CurrentUser, db: DBSession) -> None:
    portfolio = await _own(db, current_user, portfolio_id)
    await db.execute(delete(PortfolioTrade).where(PortfolioTrade.portfolio_id == portfolio_id))
    portfolio.tradebook = None
    await db.commit()


@router.get("/updates", response_model=PortfolioUpdatesResponse)
async def get_portfolio_updates(current_user: CurrentUser, db: DBSession) -> PortfolioUpdatesResponse:
    """Every portfolio valued now, with the last week's news and the next two weeks' events on each stock."""
    from app.services.holding_updates import holding_updates
    from app.services.nse_market import event_feeds

    user_id = int(current_user["id"])
    portfolios = (await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id).order_by(desc(Portfolio.updated_at))
    )).scalars().all()
    tickers = {p.ticker for pf in portfolios for p in pf.positions}
    today = utcnow().date()
    try:
        events = await event_feeds(today) if any(_is_indian(t) for t in tickers) else {}
    except Exception as e:  # NSE down: the rest of the feed still shows
        logger.warning(f"Event feeds unavailable for portfolio updates: {e}")
        events = {}
    news = await holding_updates(db, tickers, user_id, current_user.get("risk_level") or "Moderate", events, today)
    out: list[PortfolioUpdates] = []
    for pf in portfolios:
        held = {p.ticker for p in pf.positions}
        out.append(PortfolioUpdates(
            portfolio_id=pf.id,
            name=pf.name,
            performance=await _valuation(db, pf),
            updates={t: [HoldingUpdateOut(**vars(u)) for u in news[t]] for t in held if t in news},
        ))
    return PortfolioUpdatesResponse(portfolios=out)


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
        funds=_funds_out(portfolio),
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

    if request.funds is not None:
        await _verify_funds(db, request.funds)
        for old in list(portfolio.funds):
            await db.delete(old)
        portfolio.funds.clear()
        await db.flush()
        for fund in request.funds:
            db.add(PortfolioFund(portfolio_id=portfolio.id, **fund.model_dump()))

    portfolio.updated_at = utcnow()
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
        funds=_funds_out(portfolio),
        created_at=portfolio.created_at or utcnow(),
        updated_at=portfolio.updated_at or utcnow(),
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




@router.get("/{portfolio_id}/performance", response_model=PortfolioPerformance)
async def get_portfolio_performance(
    portfolio_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> PortfolioPerformance:
    """Value each position at the latest price, refreshing quotes older than 15 minutes."""
    portfolio = (
        await db.execute(
            select(Portfolio).where(
                Portfolio.id == portfolio_id, Portfolio.user_id == int(current_user["id"])
            )
        )
    ).scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return await _valuation(db, portfolio)


async def _valuation(db: DBSession, portfolio: Portfolio) -> PortfolioPerformance:
    """Holdings at the latest price (stocks, refreshing quotes older than 15 minutes) or NAV (funds)."""
    from app.services.price_service import refresh_prices

    positions = [p for p in portfolio.positions if p.shares > 0]
    weight_only = [p.ticker for p in portfolio.positions if p.shares <= 0]
    tickers = [p.ticker for p in positions]

    stocks = {
        s.ticker: s
        for s in (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))).scalars()
    }
    cutoff = utcnow() - PRICE_MAX_AGE

    def _is_stale(t: str) -> bool:
        updated = stocks[t].price_updated_at if t in stocks else None
        return updated is None or updated < cutoff

    etfs = set((await db.execute(
        select(ListedSecurity.ticker).where(ListedSecurity.ticker.in_(tickers), ListedSecurity.is_etf)
    )).scalars())
    stale = [t for t in tickers if _is_stale(t)]
    if stale:
        await refresh_prices(db, stale)

    holdings: list[HoldingPerformance] = []
    for pos in positions:
        stock = stocks.get(pos.ticker)
        price = stock.price if stock else None
        prev = stock.previous_close if stock else None
        cost_value = pos.shares * pos.cost_basis
        market_value = pos.shares * price if price is not None else None
        pnl = market_value - cost_value if market_value is not None and pos.cost_basis > 0 else None
        holdings.append(
            HoldingPerformance(
                ticker=pos.ticker,
                name=(stock.name if stock and stock.name else pos.ticker),
                sector=(stock.sector if stock else None) or ("ETF" if pos.ticker in etfs else None),
                currency="INR" if _is_indian(pos.ticker) else "USD",
                shares=pos.shares,
                avg_cost=pos.cost_basis,
                price=price,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=(pnl / cost_value * 100) if pnl is not None and cost_value else None,
                day_change=pos.shares * (price - prev) if price is not None and prev else None,
            )
        )

    for pf in portfolio.funds:  # valued at the latest NAV; AMFI publishes one a day
        fund = pf.fund
        fund_cost = pf.units * pf.cost_basis
        fund_value = pf.units * fund.nav
        fund_pnl = fund_value - fund_cost if pf.cost_basis > 0 else None
        holdings.append(
            HoldingPerformance(
                kind="fund",
                ticker=str(pf.scheme_code),
                name=fund.name,
                sector=fund.category,
                currency="INR",
                shares=pf.units,
                avg_cost=pf.cost_basis,
                price=fund.nav,
                market_value=fund_value,
                cost_value=fund_cost,
                unrealized_pnl=fund_pnl,
                unrealized_pnl_pct=(fund_pnl / fund_cost * 100) if fund_pnl is not None and fund_cost else None,
                day_change=pf.units * (fund.nav - fund.prev_nav) if fund.prev_nav else None,
                price_date=fund.nav_date,
            )
        )

    totals: list[CurrencyTotals] = []
    for currency in sorted({h.currency for h in holdings}):
        group = [h for h in holdings if h.currency == currency]
        mv = sum(h.market_value or 0.0 for h in group)
        costed = [h for h in group if h.unrealized_pnl is not None]
        cost = sum(h.cost_value for h in costed)
        pnl = sum(h.unrealized_pnl or 0.0 for h in costed)
        sectors: dict[str, float] = {}
        for h in group:
            if h.market_value:
                h.weight_by_value = round(h.market_value / mv * 100, 2) if mv else None
                key = h.sector or "Unclassified"
                sectors[key] = sectors.get(key, 0.0) + h.market_value
        totals.append(
            CurrencyTotals(
                currency=currency,
                market_value=round(mv, 2),
                cost_value=round(cost, 2),
                unrealized_pnl=round(pnl, 2),
                unrealized_pnl_pct=round(pnl / cost * 100, 2) if cost else None,
                day_change=round(sum(h.day_change or 0.0 for h in group), 2),
                sector_allocation={k: round(v / mv * 100, 2) for k, v in sectors.items()} if mv else {},
            )
        )

    times = [s.price_updated_at for t in tickers if (s := stocks.get(t)) and s.price_updated_at]
    return PortfolioPerformance(
        portfolio_id=portfolio.id,
        holdings=holdings,
        totals=totals,
        prices_as_of=min(times) if times else None,
        weight_only_tickers=weight_only,
    )


class FundMatchRow(BaseModel):
    """One fund row from a broker's export: its ISIN when the file has one, else its name."""

    isin: str | None = Field(None, max_length=12)
    name: str | None = Field(None, max_length=255)


class FundMatchRequest(BaseModel):
    funds: list[FundMatchRow] = Field(..., max_length=500)


class FundMatch(BaseModel):
    scheme_code: int
    name: str
    nav: float


class FundMatchResponse(BaseModel):
    matches: list[FundMatch | None] = Field(..., description="Same order as the request; None when no single scheme fits")


@router.post("/funds/match", response_model=FundMatchResponse)
async def match_fund_rows(request: FundMatchRequest, current_user: CurrentUser, db: DBSession) -> FundMatchResponse:
    """The AMFI scheme each imported row means. A listed ETF's ISIN gives None, since it's held as a stock."""
    found = await match_funds(db, [(r.isin, r.name) for r in request.funds])
    return FundMatchResponse(
        matches=[FundMatch(scheme_code=f.scheme_code, name=f.name, nav=f.nav) if f else None for f in found]
    )


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
    risk_free_pct: float = Field(0.0, description="risk-free rate used, weighted by holding (%)")
    equity_premium_pct: float = Field(0.0, description="equity premium used, weighted by holding (%)")


# CAPM inputs per market: (risk-free rate, equity risk premium). India: about the 10-year G-sec yield
# (7.1-7.3% in Nov 2026) and a 7% premium (estimates for 2026 run about 6.9-9%). Review yearly.
CAPM = {"IN": (0.072, 0.070), "US": (0.025, 0.055)}


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Portfolio weights must sum to 1.0 (got {total_weight:.3f})",
        )

    # Fallbacks for tickers without price history
    DEFAULT_METRICS = {
        "TLT": {"volatility": 0.08, "beta": 0.15, "max_dd": -0.12},
        "GLD": {"volatility": 0.12, "beta": 0.05, "max_dd": -0.15},
        "BIL": {"volatility": 0.01, "beta": 0.00, "max_dd": -0.01},
    }
    GENERIC_EQUITY = {"volatility": 0.25, "beta": 1.0, "max_dd": -0.30}

    tickers = [item.ticker.upper() for item in request.stocks]
    weights = [item.weight for item in request.stocks]
    markets = {t: "IN" if t.endswith((".NS", ".BO")) else "US" for t in tickers}
    benchmarks = {t: "^NSEI" if markets[t] == "IN" else "^GSPC" for t in tickers}
    rf = sum(w * CAPM[markets[t]][0] for t, w in zip(tickers, weights, strict=True))
    equity_premium = sum(w * CAPM[markets[t]][1] for t, w in zip(tickers, weights, strict=True))
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
                beta = db_stock.beta if db_stock and db_stock.beta is not None and markets[t] == "US" else 1.0
        else:
            estimated.append(t)
            m = DEFAULT_METRICS.get(t, GENERIC_EQUITY)
            vol, max_dd = m["volatility"], m["max_dd"]
            # Yahoo's stored beta is against the S&P 500, near 0 for an Indian stock, so India assumes the market's 1.0
            beta = db_stock.beta if db_stock and db_stock.beta is not None and markets[t] == "US" else m["beta"]

        vols.append(vol)
        market_rf, market_premium = CAPM[markets[t]]
        returns.append(market_rf + beta * market_premium)
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
        risk_free_pct=round(rf * 100, 2),
        equity_premium_pct=round(equity_premium * 100, 2),
    )
