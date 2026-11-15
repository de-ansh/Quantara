"""Tax harvesting on listed Indian shares from a broker tradebook (Indian rules from 23 July 2024).

Lots are matched first in, first out, as the tax rules require for shares held in demat. A lot is
long-term once held for more than 12 months. Per financial year (April to March), short-term gains are
taxed at 20% and long-term gains at 12.5% on the amount above ₹1.25 lakh, both plus 4% cess.
Short-term losses offset short- or long-term gains; long-term losses offset only long-term gains.

Splits and bonuses aren't in a tradebook, and they're taxed differently (a split spreads the cost; a
bonus share costs nothing and starts its own holding period), which Yahoo's split history can't tell
apart. So a stock with one after its first trade is left out with a warning rather than guessed at.
shortcut: demergers (e.g. ITC Hotels from ITC) aren't detected, grandfathering for shares bought before
February 2018 and surcharge are ignored.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta

STCG_RATE = 0.20
LTCG_RATE = 0.125
CESS = 0.04
LTCG_EXEMPTION = 125_000.0
SOON_DAYS = 30  # a lot with a gain turning long-term within this many days is worth waiting for


@dataclass
class Trade:
    symbol: str
    day: date
    side: str  # "buy" | "sell"
    quantity: float
    price: float


@dataclass
class Lot:
    symbol: str
    bought: date
    quantity: float
    cost: float  # per share


@dataclass
class Realized:
    short_term: float = 0.0  # net gain (negative: net loss)
    long_term: float = 0.0


@dataclass
class Book:
    lots: list[Lot]
    realized: Realized
    warnings: list[str] = field(default_factory=list)


def long_term_from(bought: date) -> date:
    """First day a lot bought on `bought` counts as long-term (held more than 12 months)."""
    try:
        anniversary = bought.replace(year=bought.year + 1)
    except ValueError:  # bought on 29 February
        anniversary = date(bought.year + 1, 3, 1) - timedelta(days=1)
    return anniversary + timedelta(days=1)


def fy_start(today: date) -> date:
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1)


def _drop_intraday(trades: list[Trade]) -> list[Trade]:
    """Remove buys and sells of a stock squared off on the same day: that's speculative business income."""
    by_day: dict[tuple[str, date], list[Trade]] = defaultdict(list)
    for t in trades:
        by_day[(t.symbol, t.day)].append(t)
    kept: list[Trade] = []
    for group in by_day.values():
        bought = sum(t.quantity for t in group if t.side == "buy")
        sold = sum(t.quantity for t in group if t.side == "sell")
        squared = min(bought, sold)
        for side in ("buy", "sell"):
            left = squared
            for t in (t for t in group if t.side == side):
                take = min(left, t.quantity)
                left -= take
                if t.quantity - take > 1e-9:
                    kept.append(Trade(t.symbol, t.day, side, t.quantity - take, t.price))
    return kept


def build_book(trades: list[Trade], today: date, splits: dict[str, list[date]] | None = None) -> Book:
    """Open lots after FIFO matching, and this financial year's realised gains.

    `splits` maps a symbol to its split or bonus dates; a stock with one after its first trade is left out.
    """
    start = fy_start(today)
    open_lots: dict[str, deque[Lot]] = defaultdict(deque)
    realized = Realized()
    broken: set[str] = set()
    warnings: list[str] = []
    first_trade: dict[str, date] = {}
    for t in trades:
        first_trade[t.symbol] = min(first_trade.get(t.symbol, t.day), t.day)
    for symbol, days in (splits or {}).items():
        after = sorted(d for d in days if symbol in first_trade and first_trade[symbol] < d <= today)
        if after:
            broken.add(symbol)
            warnings.append(
                f"{symbol}: had a bonus or split on {after[-1].isoformat()}, after your first trade, which the "
                "tradebook doesn't show, so it's left out (its realised gains too). Check it with your broker's tax P&L report"
            )
    # Within a day, buys go first so a delivery sell can use that day's earlier buy
    for t in sorted(_drop_intraday(trades), key=lambda t: (t.day, t.side != "buy")):
        if t.symbol in broken:
            continue
        lots = open_lots[t.symbol]
        if t.side == "buy":
            lots.append(Lot(t.symbol, t.day, t.quantity, t.price))
            continue
        left = t.quantity
        while left > 1e-9 and lots:
            lot = lots[0]
            take = min(left, lot.quantity)
            if t.day >= start:
                gain = take * (t.price - lot.cost)
                if t.day >= long_term_from(lot.bought):
                    realized.long_term += gain
                else:
                    realized.short_term += gain
            lot.quantity -= take
            left -= take
            if lot.quantity <= 1e-9:
                lots.popleft()
        if left > 1e-9:
            broken.add(t.symbol)
            open_lots.pop(t.symbol, None)
            warnings.append(
                f"{t.symbol}: sold {left:g} more shares than the files show being bought (a bonus or split, "
                "or trades before the earliest file), so it's left out"
            )
    remaining = [lot for symbol, q in open_lots.items() if symbol not in broken for lot in q]
    return Book(remaining, realized, warnings)


def tax_on(short_term: float, long_term: float) -> float:
    """This year's tax on net short- and long-term gains after set-off, with cess."""
    if short_term < 0:  # a short-term loss also offsets long-term gains
        long_term, short_term = long_term + short_term, 0.0
    taxable_long = max(0.0, long_term - LTCG_EXEMPTION)
    return (max(0.0, short_term) * STCG_RATE + taxable_long * LTCG_RATE) * (1 + CESS)


@dataclass
class LotView:
    symbol: str
    bought: str
    quantity: float
    cost: float
    price: float
    gain: float
    long_term: bool
    long_term_from: str


def harvest_plan(book: Book, prices: dict[str, float], today: date) -> dict:
    """What to sell this financial year, with what each step saves."""
    views = []
    for lot in book.lots:
        price = prices.get(lot.symbol)
        if price is None:
            continue
        lt = today >= long_term_from(lot.bought)
        views.append(LotView(lot.symbol, lot.bought.isoformat(), round(lot.quantity, 4), round(lot.cost, 2), price,
                             round(lot.quantity * (price - lot.cost), 2), lt, long_term_from(lot.bought).isoformat()))
    r = book.realized
    now_tax = tax_on(r.short_term, r.long_term)

    # 1. Tax-free gains: realise long-term gains up to what's left of the exemption (net of any short-term
    # loss set off against them). Biggest lot gains first, so the allowance fills with the fewest sales.
    exemption_left = max(0.0, LTCG_EXEMPTION - max(0.0, r.long_term + min(0.0, r.short_term)))
    room = exemption_left
    tax_free: list[dict] = []
    for v in sorted((v for v in views if v.long_term and v.gain > 0), key=lambda v: -v.gain):
        if room <= 1:
            break
        per_share = v.gain / v.quantity
        qty = min(v.quantity, int(room // per_share) if per_share > 0 else 0)
        if qty <= 0:
            continue
        gain = round(qty * per_share, 2)
        tax_free.append({"symbol": v.symbol, "bought": v.bought, "quantity": qty, "gain": gain})
        room -= gain
    harvested = sum(float(x["gain"]) for x in tax_free)

    # 2. Losses: selling every losing lot now, and the tax it saves on this year's gains
    losses = [v for v in views if v.gain < 0]
    st_loss = sum(v.gain for v in losses if not v.long_term)
    lt_loss = sum(v.gain for v in losses if v.long_term)
    with_losses = tax_on(r.short_term + st_loss, r.long_term + lt_loss)

    # 3. Gains about to turn long-term: waiting moves them from 20% to 12.5%
    soon = [
        {"symbol": v.symbol, "bought": v.bought, "quantity": v.quantity, "gain": v.gain,
         "long_term_from": v.long_term_from,
         "tax_if_sold_now": round(v.gain * STCG_RATE * (1 + CESS), 2)}
        for v in views
        if not v.long_term and v.gain > 0 and date.fromisoformat(v.long_term_from) <= today + timedelta(days=SOON_DAYS)
    ]
    return {
        "financial_year": f"{fy_start(today).year}-{str(fy_start(today).year + 1)[2:]}",
        "realized_short_term": round(r.short_term, 2),
        "realized_long_term": round(r.long_term, 2),
        "tax_so_far": round(now_tax, 2),
        "exemption_left": round(exemption_left, 2),
        "tax_free_harvest": tax_free,
        "tax_free_total": round(harvested, 2),
        "tax_free_future_saving": round(harvested * LTCG_RATE * (1 + CESS), 2),
        "loss_harvest": [
            {"symbol": v.symbol, "bought": v.bought, "quantity": v.quantity, "loss": v.gain, "long_term": v.long_term}
            for v in sorted(losses, key=lambda v: v.gain)
        ],
        "loss_harvest_saving": round(now_tax - with_losses, 2),
        "turning_long_term": soon,
        "lots": [v.__dict__ for v in views],
        "warnings": book.warnings,
    }
