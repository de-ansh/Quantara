"""Market-wide Indian data from NSE's public feeds: indices, flows, events and theme baskets.

Feeds are cached in process. If NSE refuses a request the last good copy is served, and with no
copy the caller gets None, so the page says "unavailable" rather than showing invented numbers.
"""

import asyncio
import re
import time
from datetime import date, datetime
from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.stock_directory import parse_index_members

logger = get_logger(__name__)

BASE = "https://www.nseindia.com/"
INDEX_FILES = "https://archives.nseindia.com/content/indices/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": BASE,
}
FETCH_DEADLINE = 25.0
LIVE_TTL = 120.0
EVENTS_TTL = 3600.0
THEME_TTL = 24 * 3600.0
MAX_EVENT_ROWS = 300
PAST_IPOS = 30

HEADLINE_INDICES = ("NIFTY 50", "NIFTY NEXT 50", "NIFTY BANK", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 100", "INDIA VIX")
BREADTH_INDEX = "NIFTY 500"
# Theme baskets are NSE's own index constituents, so membership stays current without curation
THEMES = {
    "Defence": "ind_niftyindiadefence_list.csv",
    "Digital India": "ind_niftyindiadigital_list.csv",
    "Manufacturing": "ind_niftyindiamanufacturing_list.csv",
    "Infrastructure": "ind_niftyinfralist.csv",
    "Energy": "ind_niftyenergylist.csv",
    "Consumption": "ind_niftyconsumptionlist.csv",
    "Public sector": "ind_niftycpselist.csv",
    "Tourism": "ind_niftyindiatourism_list.csv",
    "Healthcare": "ind_niftyhealthcarelist.csv",
    "Auto": "ind_niftyautolist.csv",
    "Banks": "ind_niftybanklist.csv",
    "Realty": "ind_niftyrealtylist.csv",
}

_cache: dict[str, tuple[float, Any]] = {}


async def _cached(key: str, ttl: float, fetch: Any) -> Any:
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < ttl:
        return cached[1]
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as client:
            data = await asyncio.wait_for(fetch(client), FETCH_DEADLINE)  # httpx's timeout is per read, not total
    except (httpx.HTTPError, ValueError, TimeoutError) as e:  # NSE often refuses scripts; the next request retries
        logger.warning(f"NSE feed unavailable ({key}): {e}")
        return cached[1] if cached else None
    if ttl > 0:  # ttl 0: per-company lookups that would only pile up in memory
        _cache[key] = (time.monotonic(), data)
    return data


async def nse_json(path: str, ttl: float = LIVE_TTL) -> Any:
    async def fetch(client: httpx.AsyncClient) -> Any:
        await client.get(BASE)  # the API needs the cookies this sets
        resp = await client.get(BASE + path)
        resp.raise_for_status()
        return resp.json()

    return await _cached(path, ttl, fetch)


async def _index_file(filename: str) -> str | None:
    async def fetch(client: httpx.AsyncClient) -> str:
        resp = await client.get(INDEX_FILES + filename)
        resp.raise_for_status()
        return resp.text

    result: str | None = await _cached(filename, THEME_TTL, fetch)
    return result


def _num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(str(value).strip().title(), fmt).date()
        except ValueError:
            continue
    return None


def _iso(value: Any) -> str | None:
    parsed = _date(value)
    return parsed.isoformat() if parsed else None


def _index_row(row: dict) -> dict:
    return {
        "name": row.get("index"),
        "last": _num(row.get("last")),
        "change": _num(row.get("variation")),
        "change_pct": _num(row.get("percentChange")),
    }


def parse_indices(rows: list[dict]) -> dict:
    """Headline indices, sector indices (best first) and advances/declines from NSE's index feed."""
    by_name = {r.get("index"): r for r in rows}
    headline = [_index_row(by_name[n]) for n in HEADLINE_INDICES if n in by_name]
    sectors = [_index_row(r) for r in rows if r.get("key") == "SECTORAL INDICES"]
    sectors.sort(key=lambda s: s["change_pct"] if s["change_pct"] is not None else float("-inf"), reverse=True)
    wide = by_name.get(BREADTH_INDEX)
    breadth = {k: int(_num(wide.get(k)) or 0) for k in ("advances", "declines", "unchanged")} if wide else None
    return {"headline": headline, "sectors": sectors, "breadth": breadth}


def parse_flows(rows: list[dict]) -> list[dict]:
    """Institutional cash-market flows in crore."""
    return [
        {
            "category": r.get("category"),
            "date": _iso(r.get("date")),
            "buy": _num(r.get("buyValue")),
            "sell": _num(r.get("sellValue")),
            "net": _num(r.get("netValue")),
        }
        for r in rows
    ]


def parse_earnings(rows: list[dict], today: date) -> list[dict]:
    """Board meetings about results from today on, soonest first."""
    out = []
    for r in rows:
        when = _date(r.get("date"))
        if when and when >= today and "result" in str(r.get("purpose", "")).lower():
            out.append({
                "ticker": f"{r.get('symbol')}.NS",
                "company": r.get("company"),
                "date": when.isoformat(),
                "detail": r.get("bm_desc"),
            })
    return sorted(out, key=lambda e: str(e["date"]))[:MAX_EVENT_ROWS]


def action_kind(subject: str) -> str:
    # Checked in this order so "bonus and dividend" style subjects land on the rarer event
    for kind, pattern in (("Bonus", r"\bbonus\b"), ("Split", r"\bsplit\b|sub-?division"), ("Rights", r"\brights?\b"),
                          ("Buyback", r"buy\s?-?back"), ("Dividend", r"dividend")):
        if re.search(pattern, subject, re.I):
            return kind
    return "Other"


def parse_corporate_actions(rows: list[dict]) -> list[dict]:
    out = [
        {
            "ticker": f"{r.get('symbol')}.NS",
            "company": r.get("comp"),
            "subject": r.get("subject"),
            "kind": action_kind(str(r.get("subject", ""))),
            "ex_date": _iso(r.get("exDate")),
            "record_date": _iso(r.get("recDate")),
        }
        for r in rows
    ]
    return sorted(out, key=lambda a: str(a["ex_date"] or "9999"))[:MAX_EVENT_ROWS]


def _ipo(row: dict, status: str) -> dict:
    # Current and upcoming feeds name the dates issueStartDate; the past-issues feed uses ipoStartDate
    return {
        "symbol": row.get("symbol"),
        "company": row.get("companyName") or row.get("company"),
        "status": status,
        "start_date": _iso(row.get("issueStartDate") or row.get("ipoStartDate")),
        "end_date": _iso(row.get("issueEndDate") or row.get("ipoEndDate")),
        "listing_date": _iso(row.get("listingDate")),
        "price": row.get("priceRange") or row.get("issuePrice"),
        "segment": row.get("securityType") or row.get("series"),
        "subscribed_times": _num(row.get("noOfTime")),
    }


def parse_ipos(current: list[dict] | None, upcoming: list[dict] | None, past: list[dict] | None) -> list[dict]:
    """Open issues, then upcoming, then the most recent listings."""
    return (
        [_ipo(r, "Open") for r in current or []]
        + [_ipo(r, "Upcoming") for r in upcoming or []]
        + [_ipo(r, "Listed") for r in (past or [])[:PAST_IPOS]]
    )


def _rows(data: Any) -> list[dict] | None:
    rows = data.get("data") if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else None


async def market_feeds() -> tuple[dict | None, list[dict] | None]:
    indices, flows = await asyncio.gather(nse_json("api/allIndices"), nse_json("api/fiidiiTradeReact"))
    index_rows, flow_rows = _rows(indices), _rows(flows)
    return (
        parse_indices(index_rows) if index_rows is not None else None,
        parse_flows(flow_rows) if flow_rows is not None else None,
    )


async def event_feeds(today: date) -> dict:
    earnings, actions, current, upcoming, past = await asyncio.gather(
        nse_json("api/event-calendar", EVENTS_TTL),
        nse_json("api/corporates-corporateActions?index=equities", EVENTS_TTL),
        nse_json("api/ipo-current-issue", EVENTS_TTL),
        nse_json("api/all-upcoming-issues?category=ipo", EVENTS_TTL),
        nse_json("api/public-past-issues", EVENTS_TTL),
    )
    earning_rows, action_rows = _rows(earnings), _rows(actions)
    current_rows, upcoming_rows, past_rows = _rows(current), _rows(upcoming), _rows(past)
    have_ipos = current_rows is not None or upcoming_rows is not None or past_rows is not None
    return {
        "earnings": parse_earnings(earning_rows, today) if earning_rows is not None else None,
        "corporate_actions": parse_corporate_actions(action_rows) if action_rows is not None else None,
        "ipos": parse_ipos(current_rows, upcoming_rows, past_rows) if have_ipos else None,
    }


async def theme_members() -> dict[str, list[dict]]:
    """Theme name -> members; a theme whose NSE file can't be read is left out."""
    names = list(THEMES)
    files = await asyncio.gather(*(_index_file(THEMES[n]) for n in names))
    return {name: parse_index_members(text) for name, text in zip(names, files, strict=True) if text}
