"""Balance check and rebalancing plan for one portfolio, against the user's target mix.

Flags: one company or sector over its limit, an asset mix drifted from target, holdings the app rates Avoid, and
stocks also held in another portfolio. The plan says what to sell and where to add to get back on target. Rules
of thumb, not advice.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

CLASSES = ("equity", "debt", "cash", "gold")
DRIFT_PCT = 5.0  # points off target before selling is worth the tax and trouble
# Starting points per risk profile until the user sets their own; equity stays under the profile's usual ceiling
DEFAULT_MIX = {
    "Conservative": {"equity": 50.0, "debt": 35.0, "cash": 10.0, "gold": 5.0},
    "Moderate": {"equity": 70.0, "debt": 20.0, "cash": 5.0, "gold": 5.0},
    "Aggressive": {"equity": 85.0, "debt": 5.0, "cash": 5.0, "gold": 5.0},
}

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
    unrealized_pnl: float | None


@dataclass
class Target:
    equity: float
    debt: float
    cash: float
    gold: float
    max_stock: float = 20.0  # one company, % of the portfolio
    max_sector: float = 35.0  # one sector, counting directly held stocks only
    is_default: bool = True

    @classmethod
    def load(cls, saved: dict | None, risk_level: str | None) -> "Target":
        if saved:
            return cls(**{k: float(saved[k]) for k in (*CLASSES, "max_stock", "max_sector")}, is_default=False)
        mix = DEFAULT_MIX.get(risk_level or "", DEFAULT_MIX["Moderate"])
        return cls(mix["equity"], mix["debt"], mix["cash"], mix["gold"])

    def share(self, cls_: str) -> float:
        return float(getattr(self, cls_))


@dataclass
class BalanceFlag:
    kind: Literal["stock", "sector", "mix", "verdict", "elsewhere"]
    title: str
    detail: str
    currency: str
    ticker: str | None = None
    amount: float | None = None  # how much to sell to get back under the limit


@dataclass
class Trade:
    action: Literal["sell", "add"]
    asset_class: str
    amount: float
    currency: str
    ticker: str | None = None
    name: str | None = None
    reason: str = ""
    gain: float | None = None  # profit (or loss, negative) the sale realises, before tax


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
    return max(0.0, (value - cap * total) / (1 - cap)) if cap < 1 else 0.0


def _companies(group: Sequence[Holding]) -> list[Holding]:
    """Single companies; funds and ETFs are already spread across many."""
    return [h for h in group if h.kind == "stock" and h.sector != "ETF" and asset_class(h) == "equity"]


def balance_flags(
    holdings: Sequence[Holding],
    verdicts: dict[str, str],
    elsewhere: dict[str, list[str]],
    target: Target,
    scope: str = "this portfolio",
) -> tuple[list[BalanceFlag], dict[str, dict[str, float]]]:
    """Flags, most pressing first, and the asset mix (whole % by class) for each currency."""
    flags: list[BalanceFlag] = []
    mixes: dict[str, dict[str, float]] = {}
    for currency in sorted({h.currency for h in holdings}):
        group = [h for h in holdings if h.currency == currency and h.market_value]
        total = sum(h.market_value or 0.0 for h in group)
        if not total:
            continue
        mix: dict[str, float] = {}
        for h in group:
            mix[asset_class(h)] = mix.get(asset_class(h), 0.0) + (h.market_value or 0.0) / total * 100
        mixes[currency] = {k: round(v) for k, v in mix.items()}  # whole %, as the flags quote it

        companies = _companies(group)
        for h in sorted(companies, key=lambda h: -(h.market_value or 0)):
            pct = (h.market_value or 0) / total * 100
            if pct > target.max_stock:
                flags.append(BalanceFlag(
                    "stock", f"{h.name} is {pct:.0f}% of {scope}",
                    f"One company above {target.max_stock:.0f}% means a single bad result moves the whole portfolio. "
                    f"Selling this much brings it to {target.max_stock:.0f}%, or add new money elsewhere instead.",
                    currency, h.ticker, round(trim_to(h.market_value or 0, total, target.max_stock), 2)))

        sectors: dict[str, float] = {}
        for h in companies:
            if h.sector:
                sectors[h.sector] = sectors.get(h.sector, 0.0) + (h.market_value or 0)
        for sector, value in sorted(sectors.items(), key=lambda kv: -kv[1]):
            pct = value / total * 100
            if pct > target.max_sector:
                flags.append(BalanceFlag(
                    "sector", f"{sector} is {pct:.0f}% of {scope}",
                    f"Stocks in one sector tend to fall together. Above {target.max_sector:.0f}%, new money is better "
                    "spent elsewhere, or trim this much from the sector.",
                    currency, None, round(trim_to(value, total, target.max_sector), 2)))

        off = [c for c in CLASSES if abs(mixes[currency].get(c, 0) - target.share(c)) > DRIFT_PCT]
        if off:
            worst = max(off, key=lambda c: abs(mixes[currency].get(c, 0) - target.share(c)))
            flags.append(BalanceFlag(
                "mix", f"{worst.capitalize()} is {mixes[currency].get(worst, 0):.0f}%; your target is {target.share(worst):.0f}%",
                "Off target: " + ", ".join(f"{c} {mixes[currency].get(c, 0):.0f}% vs {target.share(c):.0f}%" for c in off)
                + ". The rebalancing plan below says what to move.",
                currency))

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


def rebalance_plan(
    holdings: Sequence[Holding],
    target: Target,
    verdicts: dict[str, str],
    new_money: float = 0.0,
    currency: str = "INR",
) -> list[Trade]:
    """Sells and adds that bring one currency's holdings to the target mix, new money going in first.

    Small drifts (under DRIFT_PCT) aren't sold, only topped up with new money. Within a class that is over target,
    sells go Avoid-rated first, then over the company limit, then losses (no tax, and they offset gains), then the
    smallest gains.
    """
    group = [h for h in holdings if h.currency == currency and h.market_value]
    held = sum(h.market_value or 0.0 for h in group)
    total = held + new_money
    if not total:
        return []
    current = {c: sum(h.market_value or 0.0 for h in group if asset_class(h) == c) for c in CLASSES}
    desired = {c: target.share(c) / 100 * total for c in CLASSES}
    over = {c: current[c] - desired[c] for c in CLASSES
            if current[c] - desired[c] > 0 and (current[c] - desired[c]) / total * 100 > DRIFT_PCT}
    under = {c: desired[c] - current[c] for c in CLASSES if desired[c] > current[c]}

    trades: list[Trade] = []
    for c, excess in over.items():
        def priority(h: Holding) -> tuple:
            pnl_pct = (h.unrealized_pnl or 0) / (h.market_value or 1)
            too_big = h in _companies(group) and (h.market_value or 0) / held * 100 > target.max_stock
            return (verdicts.get(h.ticker) != "Avoid", not too_big, pnl_pct)

        for h in sorted((h for h in group if asset_class(h) == c), key=priority):
            if excess < 1:
                break
            amount = min(excess, h.market_value or 0)
            excess -= amount
            gain = (h.unrealized_pnl or 0) * amount / (h.market_value or 1) if h.unrealized_pnl is not None else None
            reason = ("rated Avoid" if verdicts.get(h.ticker) == "Avoid"
                      else "over your company limit" if priority(h)[1] is False
                      else "at a loss, so no tax and it offsets gains" if (gain or 0) < 0
                      else "smallest gain in this class")
            trades.append(Trade("sell", c, round(amount), currency, h.ticker, h.name, reason,
                                round(gain) if gain is not None else None))

    available = new_money + sum(t.amount for t in trades)
    need = sum(under.values())
    for c in CLASSES:
        if c in under and need:
            amount = under[c] * min(1.0, available / need)
            # New money beyond what the gaps need goes in at the target weights
            amount += max(0.0, available - need) * target.share(c) / 100
        else:
            amount = max(0.0, available - need) * target.share(c) / 100
        if amount >= 1:
            trades.append(Trade("add", c, round(amount), currency, reason="below target" if c in under else "new money"))
    return trades
