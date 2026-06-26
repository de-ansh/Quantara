"""FastAPI main application."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.database import engine, Base

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
    from app.core.database import AsyncSessionLocal
    from app.models.stock import Stock
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(select(Stock).limit(1))
            if not res.scalar():
                logger.info("Database stocks table is empty. Seeding core stocks...")
                core_stocks = [
                    Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", risk_score=14.0, research_score=85.0, price="$189.42", market_cap="2.94T", pe_ratio=25.0, beta=1.1, status="up", alpha_projection="+12.4%"),
                    Stock(ticker="MSFT", name="Microsoft Corp.", sector="Technology", risk_score=32.0, research_score=90.0, price="$415.20", market_cap="3.08T", pe_ratio=35.0, beta=1.2, status="up", alpha_projection="+8.1%"),
                    Stock(ticker="NVDA", name="NVIDIA Corp.", sector="Technology", risk_score=68.0, research_score=95.0, price="$822.79", market_cap="2.06T", pe_ratio=75.0, beta=1.7, status="neutral", alpha_projection="+21.3%"),
                    Stock(ticker="TSLA", name="Tesla Inc.", sector="Consumer Discretionary", risk_score=72.0, research_score=60.0, price="$175.22", market_cap="558.2B", pe_ratio=60.0, beta=1.5, status="down", alpha_projection="-4.2%"),
                    Stock(ticker="GOOGL", name="Alphabet Inc.", sector="Technology", risk_score=21.0, research_score=88.0, price="$151.24", market_cap="1.89T", pe_ratio=22.0, beta=1.05, status="up", alpha_projection="+11.5%"),
                    Stock(ticker="AMZN", name="Amazon.com Inc.", sector="Consumer Discretionary", risk_score=28.0, research_score=87.0, price="$178.12", market_cap="1.85T", pe_ratio=40.0, beta=1.15, status="up", alpha_projection="+14.2%"),
                    Stock(ticker="META", name="Meta Platforms Inc.", sector="Technology", risk_score=18.0, research_score=89.0, price="$496.22", market_cap="1.26T", pe_ratio=24.0, beta=1.25, status="up", alpha_projection="+16.8%")
                ]
                session.add_all(core_stocks)
                await session.commit()
                logger.info("Successfully seeded core stocks.")
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
from app.api.v1 import auth, users, research, recommendations, signals, portfolio, risk, audit, market

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(research.router, prefix="/api/v1", tags=["research"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(market.router, prefix="/api/v1/market", tags=["market"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
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
