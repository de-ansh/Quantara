"""Signals for NSE stocks from NSE's own published data.

Large deals: the day's bulk deals (each at least 0.5% of a company's shares) and block deals, netted
per stock. Net buying is bullish, net selling bearish; strength grows with the net share of the company.
Promoter pledges: shares the promoters have pledged, as a share of their holding. A high pledge is
a known risk in India (lenders can sell the shares if the price falls), so it is a bearish signal.
"""

import csv
import io
import re
from collections import defaultdict
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.large_deal import LargeDeal
from app.models.listed_security import ListedSecurity
from app.models.stock import Stock
from app.services.signal_engine import Signal, SignalType, save_signal_to_db

logger = get_logger(__name__)

BULK_DEALS = "https://archives.nseindia.com/content/equities/bulk.csv"
BLOCK_DEALS = "https://archives.nseindia.com/content/equities/block.csv"
PLEDGES = "https://www.nseindia.com/api/corporate-pledgedata?index=equities"
MIN_NET_DEAL_PCT = 0.25  # below this, buys and sells mostly offset: noise
FULL_NET_DEAL_PCT = 2.5  # net deals worth 2.5% of the company give full strength
PLEDGE_ALERT_PCT = 10.0  # promoters pledging 10%+ of their holding is the usual red flag
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}


def _num(value: str | None) -> float:
    try:
        return float((value or "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def parse_deals(*texts: str) -> dict[str, dict]:
    """NSE symbol -> the day's deals netted: buy and sell quantities, value-weighted price, date."""
    out: dict[str, dict] = defaultdict(lambda: {"buy_qty": 0.0, "sell_qty": 0.0, "value": 0.0, "deals": 0, "date": None})
    for text in texts:
        for row in csv.DictReader(io.StringIO(text)):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            symbol, side, qty = row.get("Symbol"), row.get("Buy/Sell", "").upper(), _num(row.get("Quantity Traded"))
            if not symbol or side not in ("BUY", "SELL") or qty <= 0:
                continue
            agg = out[symbol]
            agg["buy_qty" if side == "BUY" else "sell_qty"] += qty
            agg["value"] += qty * _num(row.get("Trade Price / Wght. Avg. Price"))
            agg["deals"] += 1
            agg["date"] = datetime.strptime(row["Date"], "%d-%b-%Y")
    return dict(out)


def deal_rows(text: str, kind: str) -> list[dict]:
    """One row per trade from NSE's bulk.csv or block.csv, ready for the large_deals table."""
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        side, qty, price = row.get("Buy/Sell", "").upper(), _num(row.get("Quantity Traded")), _num(row.get("Trade Price / Wght. Avg. Price"))
        if not row.get("Symbol") or side not in ("BUY", "SELL") or qty <= 0 or not row.get("Date"):
            continue
        rows.append({
            "deal_date": datetime.strptime(row["Date"], "%d-%b-%Y").date(), "kind": kind, "symbol": row["Symbol"][:20],
            "company": row.get("Security Name", "")[:200] or None, "client": row.get("Client Name", "")[:200] or "Unknown",
            "side": side, "quantity": qty, "price": price,
        })
    return rows


async def store_deals(db: AsyncSession, bulk: str | None, block: str | None) -> int:
    """Keep the day's trades; re-reading the same file adds nothing. Returns how many rows were offered."""
    rows = (deal_rows(bulk, "bulk") if bulk else []) + (deal_rows(block, "block") if block else [])
    if rows:
        await db.execute(insert(LargeDeal).values(rows).on_conflict_do_nothing(constraint="uq_large_deal"))
        await db.commit()
    return len(rows)


async def refresh_deals(db: AsyncSession) -> int:
    """Download today's bulk and block deal files and keep their trades."""
    async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
        bulk, block = [await _fetch(client, u) for u in (BULK_DEALS, BLOCK_DEALS)]
    return await store_deals(db, bulk.text if bulk else None, block.text if block else None)


def deal_signal(ticker: str, agg: dict, shares_outstanding: float) -> Signal | None:
    net_pct = (agg["buy_qty"] - agg["sell_qty"]) / shares_outstanding * 100
    if abs(net_pct) < MIN_NET_DEAL_PCT or agg["date"] is None:
        return None
    return Signal(
        ticker=ticker,
        signal_type=SignalType.LARGE_DEAL,
        strength=min(abs(net_pct) / FULL_NET_DEAL_PCT * 100, 100.0),
        confidence=80.0,  # exchange-reported trades, but who traded and why is unknown
        timestamp=agg["date"],
        metadata={"direction": "bullish" if net_pct > 0 else "bearish", "net_pct_of_company": round(net_pct, 3),
                  "buy_qty": agg["buy_qty"], "sell_qty": agg["sell_qty"], "deals": agg["deals"],
                  "source": "NSE bulk/block deals"},
    )


def _name_key(name: str) -> str:
    return re.sub(r"(limited|ltd)$", "", re.sub(r"[^a-z0-9]", "", name.lower()))


def parse_pledges(payload: dict) -> dict[str, dict]:
    """Normalised company name -> promoter pledge (NSE lists pledges by name only, not symbol)."""
    out = {}
    for r in payload.get("data") or []:
        if not r.get("comName"):
            continue
        out[_name_key(r["comName"])] = {
            "pledged_pct_of_promoter": _num(r.get("percPromoterShares")),
            "promoter_holding_pct": _num(r.get("percPromoterHolding")),
            "as_of": datetime.strptime(r["shp"], "%d-%b-%Y") if r.get("shp") else None,
        }
    return out


def pledge_signal(ticker: str, rec: dict) -> Signal | None:
    pct = rec["pledged_pct_of_promoter"]
    if pct < PLEDGE_ALERT_PCT or rec["as_of"] is None:
        return None
    return Signal(
        ticker=ticker,
        signal_type=SignalType.PROMOTER_PLEDGE,
        strength=min(pct * 1.5, 100.0),  # 10% -> 15, 40% -> 60, two-thirds or more -> 100
        confidence=90.0,
        timestamp=rec["as_of"],  # one signal per shareholding quarter
        metadata={"direction": "bearish", **{k: v for k, v in rec.items() if k != "as_of"},
                  "source": "NSE pledge disclosures"},
    )


async def _fetch(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp
    except httpx.HTTPError as e:  # nseindia.com/api often refuses scripts; try again next pass
        logger.warning(f"NSE signal source unavailable ({url}): {e}")
        return None


async def run_india_signals(db: AsyncSession) -> int:
    """Store large-deal and pledge signals for tracked NSE stocks; returns how many were found."""
    stocks = (await db.execute(select(Stock).where(Stock.ticker.ilike("%.NS")))).scalars().all()
    if not stocks:
        return 0
    async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
        bulk, block, pledges = [await _fetch(client, u) for u in (BULK_DEALS, BLOCK_DEALS, PLEDGES)]
    deals = parse_deals(*(r.text for r in (bulk, block) if r is not None))
    pledge_by_name = parse_pledges(pledges.json()) if pledges is not None else {}
    names: dict[str, str] = dict(row._tuple() for row in (await db.execute(
        select(ListedSecurity.ticker, ListedSecurity.name).where(ListedSecurity.ticker.in_([s.ticker for s in stocks]))
    )).all())

    found = []
    for stock in stocks:
        agg = deals.get(stock.ticker.removesuffix(".NS"))
        if agg and stock.market_cap and stock.price:
            found.append(deal_signal(stock.ticker, agg, stock.market_cap / stock.price))
        rec = pledge_by_name.get(_name_key(names.get(stock.ticker) or stock.name or ""))
        if rec:
            found.append(pledge_signal(stock.ticker, rec))
    signals = [s for s in found if s is not None]
    for signal in signals:
        await save_signal_to_db(db, signal)  # skips a signal already stored for the same day/quarter
    return len(signals)
