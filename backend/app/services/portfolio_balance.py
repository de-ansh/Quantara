"""Balance check for one portfolio: concentration, sector tilt, the asset mix against the risk profile, holdings the
app rates Avoid, and stocks also held in another portfolio. Rules of thumb with fixed thresholds, not advice."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

MAX_STOCK_PCT = 20.0  # one company
MAX_SECTOR_PCT = 35.0  # one sector, counting directly held stocks only
# Usual ceiling on equity for each risk profile; beyond it the portfolio swings more than the profile signed up for
MAX_EQUITY_PCT = {"Conservative": 60.0, "Moderate": 80.0}

_CASH = re.compile(r"\b(liquid|overnight|money market|1d rate)\b", re.I)
_GOLD = re.compile(r"\bgold\b|\bsilver\b", re.I)
_DEBT = re.compile(r"\b(debt|gilt|bonds?|treasury|g-sec|sdl)\b", re.I)

AssetClass = Literal["equity", "debt", "cash", "gold"]


class Holding(Protocol):
    kind: str
    ticker: str
    name: str
    sector: str | None
    currency: str
    market_value: float | None


@dataclass
class BalanceFlag:
    kind: Literal["stock", "sector", "mix", "verdict", "elsewhere"]
    title: str
    detail: str
    currency: str
    ticker: str | None = None
    amount: float | None = None  # how much to sell to get back under the limit


def asset_class(h: Holding) -> AssetClass:
    text = f"{h.name} {h.sector or ''}"
    if _CASH.search(text):
        return "cash"
    if _GOLD.search(text):
        return "gold"
    if _DEBT.search(text):
        return "debt"
    return "equity"


def trim_to(value: float, total: float, cap_pct: float) -> float:
    """Amount to sell so `value` is `cap_pct` of what remains (the proceeds leave the portfolio)."""
    cap = cap_pct / 100
    return max(0.0, (value - cap * total) / (1 - cap))


def balance_flags(
    holdings: Sequence[Holding],
    verdicts: dict[str, str],
    elsewhere: dict[str, list[str]],
    risk_level: str | None,
) -> tuple[list[BalanceFlag], dict[str, dict[str, float]]]:
    """Flags, most pressing first, and the asset mix (% by class) for each currency."""
    flags: list[BalanceFlag] = []
    mixes: dict[str, dict[str, float]] = {}
    for currency in sorted({h.currency for h in holdings}):
        group = [h for h in holdings if h.currency == currency and h.market_value]
        total = sum(h.market_value or 0.0 for h in group)
        if not total:
            continue
        mix: dict[str, float] = {}
        for h in group:
            cls = asset_class(h)
            mix[cls] = mix.get(cls, 0.0) + (h.market_value or 0.0) / total * 100
        mixes[currency] = {k: round(v) for k, v in mix.items()}  # whole %, as the flags quote it

        # Single companies; funds and ETFs are already spread across many
        companies = [h for h in group if h.kind == "stock" and h.sector != "ETF" and asset_class(h) == "equity"]
        for h in sorted(companies, key=lambda h: -(h.market_value or 0)):
            pct = (h.market_value or 0) / total * 100
            if pct > MAX_STOCK_PCT:
                flags.append(BalanceFlag(
                    "stock", f"{h.name} is {pct:.0f}% of this portfolio",
                    f"One company above {MAX_STOCK_PCT:.0f}% means a single bad result moves the whole portfolio. "
                    f"Selling this much brings it to {MAX_STOCK_PCT:.0f}%, or add new money elsewhere instead.",
                    currency, h.ticker, round(trim_to(h.market_value or 0, total, MAX_STOCK_PCT), 2)))

        sectors: dict[str, float] = {}
        for h in companies:
            if h.sector:
                sectors[h.sector] = sectors.get(h.sector, 0.0) + (h.market_value or 0)
        for sector, value in sorted(sectors.items(), key=lambda kv: -kv[1]):
            pct = value / total * 100
            if pct > MAX_SECTOR_PCT:
                flags.append(BalanceFlag(
                    "sector", f"{sector} is {pct:.0f}% of this portfolio",
                    f"Stocks in one sector tend to fall together. Above {MAX_SECTOR_PCT:.0f}%, new money is better "
                    "spent elsewhere, or trim this much from the sector.",
                    currency, None, round(trim_to(value, total, MAX_SECTOR_PCT), 2)))

        cap = MAX_EQUITY_PCT.get(risk_level or "")
        equity = mixes[currency].get("equity", 0)
        if cap is not None and equity > cap:
            equity_value = mix["equity"] / 100 * total
            flags.append(BalanceFlag(
                "mix", f"Equity is {equity}% of this portfolio",
                f"{risk_level} investors usually keep equity under {cap:.0f}%, with the rest in debt, cash or gold. "
                "Moving this much out of equity gets there.",
                currency, None, round(equity_value - cap / 100 * total, 2)))

        for h in group:
            if verdicts.get(h.ticker) == "Avoid":
                flags.append(BalanceFlag(
                    "verdict", f"{h.name} is rated Avoid for your risk profile",
                    "Its research outlook, risk or signals no longer fit. Open the stock to see why.",
                    currency, h.ticker))
            if h.ticker in elsewhere:
                flags.append(BalanceFlag(
                    "elsewhere", f"{h.name} is also in {', '.join(elsewhere[h.ticker])}",
                    "Counted together, your exposure to it is larger than this portfolio alone shows.",
                    currency, h.ticker))
    return flags, mixes
