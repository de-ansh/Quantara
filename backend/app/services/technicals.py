"""Technical indicators from daily closes."""

import pandas as pd

RSI_PERIOD = 14
MIN_CLOSES = 30


def _last(series: pd.Series) -> float | None:
    value = series.iloc[-1]
    return None if pd.isna(value) else round(float(value), 2)


def rsi(closes: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder's RSI; 100 when there were no falls in the window."""
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return (100 - 100 / (1 + gain / loss)).where(loss != 0, 100.0).where(gain.notna())


def indicators(closes: list[float]) -> dict | None:
    """Latest RSI, moving averages, MACD and 1-year range; None with too little history."""
    if len(closes) < MIN_CLOSES:
        return None
    series = pd.Series(closes, dtype=float)
    macd = series.ewm(span=12, adjust=False).mean() - series.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    price = float(series.iloc[-1])
    high, low = float(series.max()), float(series.min())
    sma = {n: _last(series.rolling(n).mean()) for n in (20, 50, 200)}
    current_rsi = _last(rsi(series))

    notes = []
    if current_rsi is not None and current_rsi >= 70:
        notes.append("RSI is above 70, a level usually read as overbought.")
    elif current_rsi is not None and current_rsi <= 30:
        notes.append("RSI is below 30, a level usually read as oversold.")
    if sma[200] is not None:
        notes.append(f"Price is {'above' if price > sma[200] else 'below'} its 200-day average.")
    if sma[50] is not None and sma[200] is not None:
        notes.append(f"The 50-day average is {'above' if sma[50] > sma[200] else 'below'} the 200-day average.")
    notes.append(f"MACD is {'above' if macd.iloc[-1] > signal.iloc[-1] else 'below'} its signal line.")

    return {
        "price": round(price, 2),
        "rsi_14": current_rsi,
        "sma_20": sma[20],
        "sma_50": sma[50],
        "sma_200": sma[200],
        "macd": _last(macd),
        "macd_signal": _last(signal),
        "high_1y": round(high, 2),
        "low_1y": round(low, 2),
        "pct_from_high": round((price / high - 1) * 100, 2) if high else None,
        "notes": notes,
    }


TURNOVER_SESSIONS = 20


def screener_snapshot(closes: list[float], volumes: list[float]) -> dict | None:
    """Screener columns from a year of daily closes and volumes; None with too little history."""
    values = indicators(closes)
    if values is None:
        return None
    price = values["price"]

    def gap(level: float | None) -> float | None:
        return round((price / level - 1) * 100, 2) if level else None

    traded = [c * v for c, v in zip(closes, volumes, strict=True) if v == v]  # v == v drops NaN volumes
    recent = traded[-TURNOVER_SESSIONS:]
    return {
        "rsi_14": values["rsi_14"],
        "sma50_gap_pct": gap(values["sma_50"]),
        "sma200_gap_pct": gap(values["sma_200"]),
        "from_high_52w_pct": values["pct_from_high"],
        "from_low_52w_pct": gap(values["low_1y"]),
        "turnover_1d": round(traded[-1], 2) if traded else None,
        "turnover_20d": round(sum(recent) / len(recent), 2) if recent else None,
    }
