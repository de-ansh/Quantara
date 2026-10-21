"""FastAPI main application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created")

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
                    risk_score=14.0,
                    research_score=85.0,
                    price="$189.42",
                    market_cap="2.94T",
                    pe_ratio=25.0,
                    beta=1.1,
                    status="up",
                    alpha_projection="+12.4%",
                ),
                Stock(
                    ticker="MSFT",
                    name="Microsoft Corp.",
                    sector="Technology",
                    risk_score=32.0,
                    research_score=90.0,
                    price="$415.20",
                    market_cap="3.08T",
                    pe_ratio=35.0,
                    beta=1.2,
                    status="up",
                    alpha_projection="+8.1%",
                ),
                Stock(
                    ticker="NVDA",
                    name="NVIDIA Corp.",
                    sector="Technology",
                    risk_score=68.0,
                    research_score=95.0,
                    price="$822.79",
                    market_cap="2.06T",
                    pe_ratio=75.0,
                    beta=1.7,
                    status="neutral",
                    alpha_projection="+21.3%",
                ),
                Stock(
                    ticker="TSLA",
                    name="Tesla Inc.",
                    sector="Consumer Discretionary",
                    risk_score=72.0,
                    research_score=60.0,
                    price="$175.22",
                    market_cap="558.2B",
                    pe_ratio=60.0,
                    beta=1.5,
                    status="down",
                    alpha_projection="-4.2%",
                ),
                Stock(
                    ticker="GOOGL",
                    name="Alphabet Inc.",
                    sector="Technology",
                    risk_score=21.0,
                    research_score=88.0,
                    price="$151.24",
                    market_cap="1.89T",
                    pe_ratio=22.0,
                    beta=1.05,
                    status="up",
                    alpha_projection="+11.5%",
                ),
                Stock(
                    ticker="AMZN",
                    name="Amazon.com Inc.",
                    sector="Consumer Discretionary",
                    risk_score=28.0,
                    research_score=87.0,
                    price="$178.12",
                    market_cap="1.85T",
                    pe_ratio=40.0,
                    beta=1.15,
                    status="up",
                    alpha_projection="+14.2%",
                ),
                Stock(
                    ticker="META",
                    name="Meta Platforms Inc.",
                    sector="Technology",
                    risk_score=18.0,
                    research_score=89.0,
                    price="$496.22",
                    market_cap="1.26T",
                    pe_ratio=24.0,
                    beta=1.25,
                    status="up",
                    alpha_projection="+16.8%",
                ),
                # Indian Bluechips (NIFTY 50)
                Stock(
                    ticker="RELIANCE.NS",
                    name="Reliance Industries Ltd",
                    sector="Energy",
                    risk_score=34.0,
                    research_score=92.0,
                    price="₹1,215.40",
                    market_cap="18.5T",
                    pe_ratio=24.5,
                    beta=1.05,
                    status="up",
                    alpha_projection="+14.8%",
                ),
                Stock(
                    ticker="TCS.NS",
                    name="Tata Consultancy Services Ltd",
                    sector="Technology",
                    risk_score=22.0,
                    research_score=94.0,
                    price="₹3,950.00",
                    market_cap="14.2T",
                    pe_ratio=28.0,
                    beta=0.85,
                    status="up",
                    alpha_projection="+11.2%",
                ),
                Stock(
                    ticker="HDFCBANK.NS",
                    name="HDFC Bank Ltd",
                    sector="Financials",
                    risk_score=26.0,
                    research_score=91.0,
                    price="₹1,680.00",
                    market_cap="12.8T",
                    pe_ratio=19.5,
                    beta=1.10,
                    status="up",
                    alpha_projection="+13.5%",
                ),
                Stock(
                    ticker="INFY.NS",
                    name="Infosys Ltd",
                    sector="Technology",
                    risk_score=24.0,
                    research_score=90.0,
                    price="₹1,820.00",
                    market_cap="7.6T",
                    pe_ratio=26.0,
                    beta=0.95,
                    status="up",
                    alpha_projection="+12.1%",
                ),
                Stock(
                    ticker="ICICIBANK.NS",
                    name="ICICI Bank Ltd",
                    sector="Financials",
                    risk_score=28.0,
                    research_score=93.0,
                    price="₹1,240.00",
                    market_cap="8.7T",
                    pe_ratio=17.5,
                    beta=1.15,
                    status="up",
                    alpha_projection="+16.4%",
                ),
                Stock(
                    ticker="TATAMOTORS.NS",
                    name="Tata Motors Ltd",
                    sector="Consumer Discretionary",
                    risk_score=48.0,
                    research_score=86.0,
                    price="₹940.00",
                    market_cap="3.4T",
                    pe_ratio=16.0,
                    beta=1.45,
                    status="neutral",
                    alpha_projection="+9.8%",
                ),
                Stock(
                    ticker="ITC.NS",
                    name="ITC Ltd",
                    sector="Consumer Staples",
                    risk_score=18.0,
                    research_score=89.0,
                    price="₹480.00",
                    market_cap="6.0T",
                    pe_ratio=25.5,
                    beta=0.65,
                    status="up",
                    alpha_projection="+8.4%",
                ),
                Stock(
                    ticker="BHARTIARTL.NS",
                    name="Bharti Airtel Ltd",
                    sector="Communication Services",
                    risk_score=25.0,
                    research_score=92.0,
                    price="₹1,650.00",
                    market_cap="9.8T",
                    pe_ratio=42.0,
                    beta=0.90,
                    status="up",
                    alpha_projection="+17.2%",
                ),
                Stock(
                    ticker="LT.NS",
                    name="Larsen & Toubro Ltd",
                    sector="Industrials",
                    risk_score=30.0,
                    research_score=91.0,
                    price="₹3,600.00",
                    market_cap="4.9T",
                    pe_ratio=32.0,
                    beta=1.10,
                    status="up",
                    alpha_projection="+15.0%",
                ),
                Stock(
                    ticker="SUNPHARMA.NS",
                    name="Sun Pharmaceutical Industries",
                    sector="Healthcare",
                    risk_score=21.0,
                    research_score=88.0,
                    price="₹1,850.00",
                    market_cap="4.4T",
                    pe_ratio=34.0,
                    beta=0.70,
                    status="up",
                    alpha_projection="+10.6%",
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

    # Start periodic background task for signal processing
    import asyncio

    from app.services.signal_engine import run_periodic_signal_processing

    # Run every hour in production, but let's check settings/env or use 3600 seconds as default
    bg_task = asyncio.create_task(run_periodic_signal_processing(interval_seconds=3600))
    app.state.bg_task = bg_task
    logger.info("Background signal processing task started")

    yield

    # Shutdown
    logger.info("Shutting down application")
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        logger.info("Background signal processing task stopped")
    except Exception as e:
        logger.error(f"Error stopping background task: {e}")

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
    recommendations,
    research,
    risk,
    signals,
    users,
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
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
