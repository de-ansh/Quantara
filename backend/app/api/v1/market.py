"""Market data API endpoints."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

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
    quotes = await _get_quotes()
    vix_val, vix_change = quotes["^VIX"]
    india_vix_val, _ = quotes["^INDIAVIX"]
    spx_val, spx_change = quotes["^GSPC"]
    nifty_val, nifty_change = quotes["^NSEI"]

    vix_snapshot = VIXSnapshot(
        value=vix_val,
        change=vix_change,
        change_percent=_pct(vix_val, vix_change),
        status=_vix_status(vix_val),
    )

    now_utc = datetime.now(UTC)

    ist_now = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    ist_mins = ist_now.hour * 60 + ist_now.minute
    is_nse_open = ist_now.weekday() < 5 and (9 * 60 + 15 <= ist_mins <= 15 * 60 + 30)

    india_market = MarketRegionInfo(
        name="NSE / BSE",
        country="India",
        index_name="NIFTY 50",
        index_value=nifty_val,
        index_change=f"{_pct(nifty_val, nifty_change):+.2f}%",
        vix=india_vix_val,
        status="OPEN" if is_nse_open else "CLOSED",
        trading_hours="09:15 - 15:30 IST",
    )

    ny_now = now_utc.astimezone(ZoneInfo("America/New_York"))
    ny_mins = ny_now.hour * 60 + ny_now.minute
    is_nyse_open = ny_now.weekday() < 5 and (9 * 60 + 30 <= ny_mins <= 16 * 60)

    us_market = MarketRegionInfo(
        name="NYSE / NASDAQ",
        country="United States",
        index_name="S&P 500",
        index_value=spx_val,
        index_change=f"{_pct(spx_val, spx_change):+.2f}%",
        vix=vix_val,
        status="OPEN" if is_nyse_open else "CLOSED",
        trading_hours="09:30 - 16:00 ET",
    )

    return MarketStatusResponse(
        vix=vix_snapshot,
        alerts=_build_alerts(quotes),
        us_market=us_market,
        india_market=india_market,
    )


# Last known levels, used when Yahoo Finance is unreachable.
_FALLBACK_QUOTES: dict[str, tuple[float, float]] = {
    "^VIX": (14.22, 0.0),
    "^INDIAVIX": (16.04, 0.0),
    "^GSPC": (5218.40, 0.0),
    "^NSEI": (22739.85, 0.0),
}
_QUOTE_TTL_SECONDS = 60.0
_quote_cache: dict[str, Any] = {"at": 0.0, "quotes": None}


def _fetch_quotes_sync() -> dict[str, tuple[float, float]]:
    """Fetch latest close and day change for each tracked symbol."""
    quotes = dict(_FALLBACK_QUOTES)
    for symbol in _FALLBACK_QUOTES:
        try:
            closes = yf.Ticker(symbol).history(period="5d", interval="1d")["Close"].dropna()
            if len(closes) >= 2:
                last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                quotes[symbol] = (round(last, 2), round(last - prev, 2))
        except Exception as e:
            logger.warning(f"Market quote fetch failed for {symbol}: {e}")
    return quotes


async def _get_quotes() -> dict[str, tuple[float, float]]:
    """Return cached quotes, refreshing at most once per TTL."""
    now = time.monotonic()
    if _quote_cache["quotes"] is None or now - _quote_cache["at"] > _QUOTE_TTL_SECONDS:
        _quote_cache["quotes"] = await asyncio.to_thread(_fetch_quotes_sync)
        _quote_cache["at"] = now
    return _quote_cache["quotes"]


def _pct(value: float, change: float) -> float:
    prev = value - change
    return round(change / prev * 100, 2) if prev else 0.0


def _vix_status(vix: float) -> str:
    if vix > 20:
        return "high"
    if vix > 15:
        return "moderate"
    return "low"


def _build_alerts(quotes: dict[str, tuple[float, float]]) -> list[MarketAlert]:
    """Derive macro alerts from the live index and volatility moves."""
    now_str = datetime.now().strftime("%H:%M:%S")
    alerts: list[MarketAlert] = []

    for symbol, label in (("^GSPC", "S&P 500"), ("^NSEI", "NIFTY 50")):
        value, change = quotes[symbol]
        pct = _pct(value, change)
        if pct >= 0.25:
            alert_type = "BULLISH"
        elif pct <= -0.25:
            alert_type = "BEARISH"
        else:
            alert_type = "NEUTRAL"
        alerts.append(
            MarketAlert(
                id=len(alerts) + 1,
                time=now_str,
                type=alert_type,
                text=f"{label} AT {value:,.2f} ({pct:+.2f}% D/D).",
            )
        )

    for symbol, label in (("^VIX", "US VIX"), ("^INDIAVIX", "INDIA VIX")):
        value, change = quotes[symbol]
        pct = _pct(value, change)
        regime = _vix_status(value).upper()
        alerts.append(
            MarketAlert(
                id=len(alerts) + 1,
                time=now_str,
                type="VOLATILITY" if abs(pct) >= 5 or value > 20 else "NEUTRAL",
                text=f"{label} AT {value:.2f} ({pct:+.2f}%). VOLATILITY REGIME: {regime}.",
            )
        )

    return alerts
