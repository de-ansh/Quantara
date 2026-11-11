"""Buy / Hold / Avoid for any stock from its numbers alone, with the pros and cons behind it.

The AI research verdict needs a paid report, so only a few stocks have one. This call needs
nothing but the fundamentals, prices and signals already stored, so every tracked stock gets one.
"""

from dataclasses import dataclass, field

from app.models.stock import Stock

# Stricter than the AI verdict's 65: at 65, 4 in 10 Nifty 500 stocks were Buys, too many to mean anything
BUY_SCORE = 70.0
AVOID_SCORE = 40.0
MAJOR_CON = -5  # heavy debt, losses, a falling price or promoters selling rule out a Buy
MIN_METRICS = 4  # fewer known numbers than this is not enough to call
RISK_BAND_MAX = {"Conservative": 33.0, "Moderate": 66.0, "Aggressive": 100.0}
RISK_SLACK = 15.0  # how far above the profile's band a stock can sit before it can't be a Buy
_FINANCIALS = ("financial", "bank")  # leverage is the business model there, so D/E isn't judged


@dataclass
class StockCall:
    verdict: str  # Buy | Hold | Avoid | Unrated
    score: float | None
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    metrics_used: int = 0


def _pct(v: float) -> str:
    return f"{v:.0f}%" if abs(v) >= 10 else f"{v:.1f}%"


def data_call(stock: Stock, risk_level: str = "Moderate", signal_score: float | None = None) -> StockCall:
    """Score around a neutral 50 from each known metric; unknown metrics count neither way."""
    points: list[tuple[float, str]] = []  # (+ is a pro, - a con, text)
    known = 0

    def rule(value: float | None, checks: list[tuple[bool, float, str]]) -> None:
        nonlocal known
        if value is None:
            return
        known += 1
        for hit, pts, text in checks:
            if hit:
                points.append((pts, text))
                return

    s = stock
    rule(s.roe_pct, [] if s.roe_pct is None else [
        (s.roe_pct >= 20, 8, f"High return on equity ({_pct(s.roe_pct)})"),
        (s.roe_pct >= 15, 4, f"Healthy return on equity ({_pct(s.roe_pct)})"),
        (s.roe_pct < 8, -6, f"Weak return on equity ({_pct(s.roe_pct)})"),
    ])
    rule(s.roce_pct, [] if s.roce_pct is None else [
        (s.roce_pct >= 20, 6, f"High return on capital employed ({_pct(s.roce_pct)})"),
        (s.roce_pct < 8, -5, f"Low return on capital employed ({_pct(s.roce_pct)})"),
    ])
    rule(s.revenue_cagr_3y_pct, [] if s.revenue_cagr_3y_pct is None else [
        (s.revenue_cagr_3y_pct >= 15, 6, f"Revenue grew {_pct(s.revenue_cagr_3y_pct)} a year over 3 years"),
        (s.revenue_cagr_3y_pct < 0, -6, f"Revenue shrank {_pct(-s.revenue_cagr_3y_pct)} a year over 3 years"),
    ])
    rule(s.profit_cagr_3y_pct, [] if s.profit_cagr_3y_pct is None else [
        (s.profit_cagr_3y_pct >= 15, 6, f"Profit grew {_pct(s.profit_cagr_3y_pct)} a year over 3 years"),
        (s.profit_cagr_3y_pct < 0, -6, f"Profit fell {_pct(-s.profit_cagr_3y_pct)} a year over 3 years"),
    ])
    rule(s.revenue_growth_pct, [] if s.revenue_growth_pct is None else [
        (s.revenue_growth_pct >= 15, 3, f"Revenue up {_pct(s.revenue_growth_pct)} in the latest year"),
        (s.revenue_growth_pct < 0, -4, f"Revenue down {_pct(-s.revenue_growth_pct)} in the latest year"),
    ])
    rule(s.profit_margin_pct, [] if s.profit_margin_pct is None else [
        (s.profit_margin_pct >= 15, 3, f"Strong profit margin ({_pct(s.profit_margin_pct)})"),
        (s.profit_margin_pct < 3, -4, f"Thin profit margin ({_pct(s.profit_margin_pct)})"),
    ])
    if not any(word in (s.sector or "").lower() for word in _FINANCIALS):
        rule(s.debt_to_equity, [] if s.debt_to_equity is None else [
            (s.debt_to_equity <= 0.3, 4, f"Little debt (debt/equity {s.debt_to_equity:.2f})"),
            (s.debt_to_equity > 1.5, -6, f"Heavy debt (debt/equity {s.debt_to_equity:.2f})"),
        ])
    rule(s.pe_ratio, [] if s.pe_ratio is None else [
        (s.pe_ratio <= 0, -8, "Loss-making (no positive earnings)"),
        (s.pe_ratio <= 20, 4, f"Reasonable valuation (P/E {s.pe_ratio:.0f})"),
        (s.pe_ratio > 60, -6, f"Expensive (P/E {s.pe_ratio:.0f})"),
        (s.pe_ratio > 40, -2, f"Rich valuation (P/E {s.pe_ratio:.0f})"),
    ])
    rule(s.return_1y_pct, [] if s.return_1y_pct is None else [
        (s.return_1y_pct >= 25, 4, f"Strong 1-year price trend (+{_pct(s.return_1y_pct)})"),
        (s.return_1y_pct <= -25, -6, f"Weak 1-year price trend ({_pct(s.return_1y_pct)})"),
    ])
    rule(s.promoter_change_pp, [] if s.promoter_change_pp is None else [
        (s.promoter_change_pp >= 1, 4, f"Promoters raised their stake by {s.promoter_change_pp:.1f} points last quarter"),
        (s.promoter_change_pp <= -2, -5, f"Promoters cut their stake by {-s.promoter_change_pp:.1f} points last quarter"),
    ])
    rule(s.dividend_yield_pct, [] if s.dividend_yield_pct is None else [
        (s.dividend_yield_pct >= 2.5, 2, f"Pays a {s.dividend_yield_pct:.1f}% dividend yield"),
    ])
    if signal_score is not None and signal_score != 50.0:
        points += [(4, "Recent signals lean bullish")] if signal_score >= 65 else []
        points += [(-4, "Recent signals lean bearish")] if signal_score <= 35 else []

    too_risky = False
    if s.risk_score is not None:
        if s.risk_score >= 75:
            points.append((-4, f"High risk score ({s.risk_score:.0f}/100)"))
        band_max = RISK_BAND_MAX.get(risk_level, RISK_BAND_MAX["Moderate"])
        if s.risk_score > band_max + RISK_SLACK:
            too_risky = True
            points.append((0, f"Riskier than a {risk_level.lower()} profile ({s.risk_score:.0f}/100)"))

    if known < MIN_METRICS:
        return StockCall("Unrated", None, metrics_used=known)
    score = max(0.0, min(100.0, 50 + sum(p for p, _ in points)))
    major_con = any(p <= MAJOR_CON for p, _ in points)
    buy = score >= BUY_SCORE and not too_risky and not major_con
    verdict = "Avoid" if score <= AVOID_SCORE else "Buy" if buy else "Hold"
    ranked = sorted(points, key=lambda p: -abs(p[0]))
    return StockCall(
        verdict=verdict,
        score=round(score, 1),
        pros=[t for p, t in ranked if p > 0][:5],
        cons=[t for p, t in ranked if p <= 0 and (p < 0 or "Riskier" in t)][:5],
        metrics_used=known,
    )
