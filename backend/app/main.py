"""FastAPI main application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Error monitoring is opt-in: nothing is sent unless SENTRY_DSN is set
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.app_version,
        send_default_pii=False,
        traces_sample_rate=0.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Schema is owned by Alembic: run `alembic upgrade head` before starting the app.

    # Seed database with core stocks if empty
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.stock import Stock

    async with AsyncSessionLocal() as session:
        try:
            core_stocks = [
                Stock(
                    ticker="AAPL",
                    name="Apple Inc.",
                    sector="Technology",
                ),
                Stock(
                    ticker="MSFT",
                    name="Microsoft Corp.",
                    sector="Technology",
                ),
                Stock(
                    ticker="NVDA",
                    name="NVIDIA Corp.",
                    sector="Technology",
                ),
                Stock(
                    ticker="TSLA",
                    name="Tesla Inc.",
                    sector="Consumer Discretionary",
                ),
                Stock(
                    ticker="GOOGL",
                    name="Alphabet Inc.",
                    sector="Technology",
                ),
                Stock(
                    ticker="AMZN",
                    name="Amazon.com Inc.",
                    sector="Consumer Discretionary",
                ),
                Stock(
                    ticker="META",
                    name="Meta Platforms Inc.",
                    sector="Technology",
                ),
                # Indian Bluechips (NIFTY 50)
                Stock(
                    ticker="RELIANCE.NS",
                    name="Reliance Industries Ltd",
                    sector="Energy",
                ),
                Stock(
                    ticker="TCS.NS",
                    name="Tata Consultancy Services Ltd",
                    sector="Technology",
                ),
                Stock(
                    ticker="HDFCBANK.NS",
                    name="HDFC Bank Ltd",
                    sector="Financials",
                ),
                Stock(
                    ticker="INFY.NS",
                    name="Infosys Ltd",
                    sector="Technology",
                ),
                Stock(
                    ticker="ICICIBANK.NS",
                    name="ICICI Bank Ltd",
                    sector="Financials",
                ),
                Stock(
                    # Post-demerger listing (TATAMOTORS.NS is delisted); quotes and
                    # fundamentals are filled in by the price refresh job.
                    ticker="TMCV.NS",
                    name="Tata Motors Ltd",
                    sector="Consumer Discretionary",
                ),
                Stock(
                    ticker="ITC.NS",
                    name="ITC Ltd",
                    sector="Consumer Staples",
                ),
                Stock(
                    ticker="BHARTIARTL.NS",
                    name="Bharti Airtel Ltd",
                    sector="Communication Services",
                ),
                Stock(
                    ticker="LT.NS",
                    name="Larsen & Toubro Ltd",
                    sector="Industrials",
                ),
                Stock(
                    ticker="SUNPHARMA.NS",
                    name="Sun Pharmaceutical Industries",
                    sector="Healthcare",
                ),
            ]
            existing_tickers = (await session.execute(select(Stock.ticker))).scalars().all()
            existing_set = set(existing_tickers)
            to_add = [s for s in core_stocks if s.ticker not in existing_set]
            if to_add:
                session.add_all(to_add)
                await session.commit()
                logger.info(f"Successfully seeded {len(to_add)} missing universe stocks.")
        except Exception as seed_err:
            logger.error(f"Error seeding database: {seed_err}")
            await session.rollback()

    # Background jobs. Every worker schedules them; Postgres advisory locks let one run each pass.
    import asyncio

    from app.services.price_service import run_periodic_price_refresh
    from app.services.signal_engine import run_periodic_signal_processing

    bg_tasks: list[asyncio.Task] = []
    if settings.enable_background_tasks:
        bg_tasks = [
            asyncio.create_task(run_periodic_signal_processing(interval_seconds=3600)),
            asyncio.create_task(run_periodic_price_refresh()),
        ]
        logger.info("Background signal processing and price refresh tasks started")
    app.state.bg_tasks = bg_tasks

    yield

    # Shutdown
    logger.info("Shutting down application")
    for task in bg_tasks:
        task.cancel()
    results = await asyncio.gather(*bg_tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            logger.error(f"Error stopping background task: {result}")

    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Risk-intelligent investment research system",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.app_version,
        "docs": "/docs" if settings.is_development else "Documentation disabled in production",
    }


# Include API routers
from app.api.v1 import (
    audit,
    auth,
    market,
    portfolio,
    price_alerts,
    recommendations,
    research,
    risk,
    signals,
    users,
    watchlist,
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(research.router, prefix="/api/v1", tags=["research"])
app.include_router(
    recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"]
)
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(market.router, prefix="/api/v1/market", tags=["market"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["watchlist"])
app.include_router(price_alerts.router, prefix="/api/v1/alerts/price", tags=["alerts"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    sentry_sdk.capture_exception(exc)  # no-op when Sentry is not configured
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
