"""Market data API endpoints."""
import math
import time
from datetime import datetime
from typing import List
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


class MarketStatusResponse(BaseModel):
    """Market status response schema."""
    vix: VIXSnapshot
    alerts: List[MarketAlert]


@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status() -> MarketStatusResponse:
    """
    Get live market VIX feed and macroeconomic alerts.
    """
    # Simulate a dynamic VIX fluctuating around 14.22
    # Use time to create a changing wave
    t = time.time()
    
    # Base VIX is 14.22, fluctuates by +/- 1.5
    wave = math.sin(t / 60.0) * 0.8 + math.cos(t / 300.0) * 0.5
    vix_val = round(14.22 + wave, 2)
    
    # Calculate change based on base 14.22
    change = round(vix_val - 14.22, 2)
    change_percent = round((change / 14.22) * 100, 2)
    
    status_str = "low"
    if vix_val > 20:
        status_str = "high"
    elif vix_val > 15:
        status_str = "moderate"
        
    vix_snapshot = VIXSnapshot(
        value=vix_val,
        change=change,
        change_percent=change_percent,
        status=status_str
    )
    
    # Dynamic macroeconomic alerts relative to current time
    now_dt = datetime.now()
    
    alerts = [
        MarketAlert(
            id=1,
            time=now_dt.replace(minute=max(0, now_dt.minute - 2)).strftime("%H:%M:%S"),
            type="BULLISH",
            text="FED RATE UPDATE: STATEMENTS SUGGEST HAWKISH PAUSE. TECH SECTOR INFLOWS DETECTED."
        ),
        MarketAlert(
            id=2,
            time=now_dt.replace(minute=max(0, now_dt.minute - 7)).strftime("%H:%M:%S"),
            type="NEUTRAL",
            text="AAPL EARNINGS CALL PREP: ANALYST CONSENSUS SHIFTING TO OVERWEIGHT FOR Q3."
        ),
        MarketAlert(
            id=3,
            time=now_dt.replace(minute=max(0, now_dt.minute - 20)).strftime("%H:%M:%S"),
            type="BEARISH",
            text="CRUDE OIL FUTURES (WTI) BREAKING BELOW $75 SUPPORT. ENERGY EXPOSURE WARNING."
        ),
        MarketAlert(
            id=4,
            time=now_dt.replace(minute=max(0, now_dt.minute - 35)).strftime("%H:%M:%S"),
            type="VOLATILITY",
            text=f"VIX FLUCTUATION DETECTED ({vix_val}). INDEX PROTECTIVE PUT VOLUME INCREASING."
        )
    ]
    
    return MarketStatusResponse(vix=vix_snapshot, alerts=alerts)
