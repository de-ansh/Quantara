"""Market data API endpoints."""

import math
import time
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class VIXSnapshot(BaseModel):
    """VIX snapshot schema."""

    value: float
    change: float
    change_percent: float
    status: str


class MarketAlert(BaseModel):
    """Market alert schema."""

    id: int
    time: str
    type: str
    text: str


class MarketRegionInfo(BaseModel):
    """Market region summary schema."""

    name: str
    country: str
    index_name: str
    index_value: float
    index_change: str
    vix: float
    status: str  # "OPEN" | "CLOSED"
    trading_hours: str


class MarketStatusResponse(BaseModel):
    """Market status response schema."""

    vix: VIXSnapshot
    alerts: list[MarketAlert]
    us_market: MarketRegionInfo | None = None
    india_market: MarketRegionInfo | None = None


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status() -> MarketStatusResponse:
    """
    Get live market VIX feed, dual-market status (US + India), and macroeconomic alerts.
    """
    import math
    import time
    from datetime import datetime, timezone, timedelta

    # Dynamic VIX simulation
    t = time.time()
    wave = math.sin(t / 60.0) * 0.8 + math.cos(t / 300.0) * 0.5
    vix_val = round(14.22 + wave, 2)
    change = round(vix_val - 14.22, 2)
    change_percent = round((change / 14.22) * 100, 2)

    status_str = "low"
    if vix_val > 20:
        status_str = "high"
    elif vix_val > 15:
        status_str = "moderate"

    vix_snapshot = VIXSnapshot(
        value=vix_val, change=change, change_percent=change_percent, status=status_str
    )

    now_utc = datetime.now(timezone.utc)

    # 1. Indian Market (IST: UTC + 5:30)
    ist_now = now_utc + timedelta(hours=5, minutes=30)
    is_ist_weekday = ist_now.weekday() < 5
    ist_time_mins = ist_now.hour * 60 + ist_now.minute
    is_nse_open = is_ist_weekday and (9 * 60 + 15 <= ist_time_mins <= 15 * 60 + 30)

    india_market = MarketRegionInfo(
        name="NSE / BSE",
        country="India",
        index_name="NIFTY 50",
        index_value=22739.85,
        index_change="+0.62%",
        vix=16.04,
        status="OPEN" if is_nse_open else "CLOSED",
        trading_hours="09:15 - 15:30 IST",
    )

    # 2. US Market (EST: UTC - 4)
    est_now = now_utc - timedelta(hours=4)
    is_est_weekday = est_now.weekday() < 5
    est_time_mins = est_now.hour * 60 + est_now.minute
    is_nyse_open = is_est_weekday and (9 * 60 + 30 <= est_time_mins <= 16 * 60)

    us_market = MarketRegionInfo(
        name="NYSE / NASDAQ",
        country="United States",
        index_name="S&P 500",
        index_value=5218.40,
        index_change="+0.45%",
        vix=vix_val,
        status="OPEN" if is_nyse_open else "CLOSED",
        trading_hours="09:30 - 16:00 EST",
    )

    # Macroeconomic alerts
    now_dt = datetime.now()
    alerts = [
        MarketAlert(
            id=1,
            time=now_dt.replace(minute=max(0, now_dt.minute - 2)).strftime("%H:%M:%S"),
            type="BULLISH",
            text="RBI MONETARY UPDATE: POLICY STANCE ACCOMMODATIVE. NIFTY BANK EXPANSION CONTINUES.",
        ),
        MarketAlert(
            id=2,
            time=now_dt.replace(minute=max(0, now_dt.minute - 7)).strftime("%H:%M:%S"),
            type="BULLISH",
            text="FED RATE UPDATE: STATEMENTS SUGGEST HAWKISH PAUSE. TECH SECTOR INFLOWS DETECTED.",
        ),
        MarketAlert(
            id=3,
            time=now_dt.replace(minute=max(0, now_dt.minute - 15)).strftime("%H:%M:%S"),
            type="NEUTRAL",
            text="RELIANCE & TCS ANNOUNCEMENTS: CAPITAL EXPENDITURE & DIGITAL INFRASTRUCTURE PIPELINE ON TRACK.",
        ),
        MarketAlert(
            id=4,
            time=now_dt.replace(minute=max(0, now_dt.minute - 25)).strftime("%H:%M:%S"),
            type="BEARISH",
            text="BRENT CRUDE AT $82/BBL. CURRENT ACCOUNT DEFICIT SENSITIVITY FLAGGED FOR REFINING/AUTO.",
        ),
        MarketAlert(
            id=5,
            time=now_dt.replace(minute=max(0, now_dt.minute - 35)).strftime("%H:%M:%S"),
            type="VOLATILITY",
            text=f"INDIA VIX AT 16.04 | US VIX AT {vix_val}. DERIVATIVES ROLLOVER BALANCED.",
        ),
    ]

    return MarketStatusResponse(
        vix=vix_snapshot,
        alerts=alerts,
        us_market=us_market,
        india_market=india_market,
    )
