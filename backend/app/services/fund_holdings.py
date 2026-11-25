"""What each held mutual fund owns, for look-through exposure: its latest monthly portfolio, from Groww.

Groww's public fund pages load from a JSON API. It's unofficial (no contract: it can change or block us), so every
step degrades to "no holdings" rather than failing a price pass. Funds publish portfolios monthly, so each held fund
is checked at most weekly, one request at a time.
"""

import asyncio
import difflib
import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.listed_security import ListedSecurity
from app.models.mutual_fund import FundHolding, MutualFund
from app.models.portfolio import PortfolioFund

logger = get_logger(__name__)

SEARCH_URL = "https://groww.in/v1/api/search/v3/query/global/st_p_query"
SCHEME_URL = "https://groww.in/v1/api/data/mf/web/v4/scheme/search/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; portfolio-tracker)", "Accept": "application/json"}
CHECK_EVERY = timedelta(days=7)
PAUSE_SECONDS = 1.0  # between requests: a handful of funds, no hurry
CANDIDATES = 4  # search results tried per fund, best name match first
IST = timedelta(hours=5, minutes=30)

# Groww's "nature" of each line to the app's asset classes; anything else (REITs, units of other funds) is "other"
KINDS = {"EQUITY": "equity", "DEBT": "debt", "CASH": "cash", "GOLD": "gold", "SILVER": "gold", "COMMODITY": "gold"}
_DROP = {"ltd", "limited", "the", "co", "company", "inc", "plc", "and"}


def norm_company(name: str) -> str:
    """Comparable company name: "HDFC Bank Ltd." and "HDFC BANK LIMITED" both become "hdfc bank"."""
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and "))
    return " ".join(w for w in words if w not in _DROP)


def parse_scheme(data: dict[str, Any]) -> tuple[date | None, list[dict[str, Any]]]:
    """The portfolio date and its lines (name, kind, sector, weight %) from one Groww scheme response."""
    rows, as_of = [], None
    for h in data.get("holdings") or []:
        try:
            weight = float(h.get("corpus_per") or 0)
        except (TypeError, ValueError):
            continue
        name = (h.get("company_name") or "").strip()
        if not name or weight <= 0:
            continue
        if h.get("portfolio_date") and as_of is None:  # "2026-10-30T18:30:00.000Z" is 31 Oct in India
            try:
                as_of = (datetime.fromisoformat(h["portfolio_date"].replace("Z", "+00:00")) + IST).date()
            except ValueError:
                pass
        rows.append({"name": name[:255], "kind": KINDS.get((h.get("nature_name") or "").upper(), "other"),
                     "sector": (h.get("sector_name") or None), "weight": weight})
    return as_of, rows


async def _get(client: httpx.AsyncClient, url: str, **params: Any) -> dict[str, Any] | None:
    await asyncio.sleep(PAUSE_SECONDS)
    try:
        resp = await client.get(url, params=params or None)
        return resp.json() if resp.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


async def fetch_scheme(client: httpx.AsyncClient, fund: MutualFund) -> tuple[str, dict[str, Any]] | None:
    """Groww's page for this exact scheme (its id and data), confirmed by AMFI scheme code; None when not found."""
    def same(data: dict[str, Any] | None) -> bool:
        return data is not None and str(data.get("scheme_code")) == str(fund.scheme_code)

    if fund.groww_id:
        data = await _get(client, SCHEME_URL.format(fund.groww_id))
        if data and same(data):
            return fund.groww_id, data
    # Groww's search is fussy about long queries: the first few words of the name find the fund family
    query = " ".join(fund.name.replace("-", " ").split()[:3])
    found = await _get(client, SEARCH_URL, page=0, query=query, size=10, web="true")
    content = ((found or {}).get("data") or {}).get("content") or []
    schemes = [c for c in content if c.get("entity_type") == "Scheme" and c.get("search_id")]
    schemes.sort(key=lambda c: -difflib.SequenceMatcher(None, (c.get("title") or "").lower(), fund.name.lower()).ratio())
    for c in schemes[:CANDIDATES]:
        data = await _get(client, SCHEME_URL.format(c["search_id"]))
        if data and same(data):
            return c["search_id"], data
        # Search lists Direct plans; a Regular plan is linked from its Direct one
        regular = (data or {}).get("regular_search_id")
        if regular:
            data = await _get(client, SCHEME_URL.format(regular))
            if data and same(data):
                return regular, data
    return None


async def _ticker_index(db: AsyncSession) -> dict[str, str]:
    """Normalised company name -> ticker for Indian listings, NSE preferred over BSE."""
    rows = (await db.execute(select(ListedSecurity.ticker, ListedSecurity.name).where(
        or_(ListedSecurity.ticker.like("%.NS"), ListedSecurity.ticker.like("%.BO")), ListedSecurity.is_etf.is_(False),
    ))).all()
    index: dict[str, str] = {}
    for ticker, name in sorted(rows, key=lambda r: r[0].endswith(".NS")):  # .NS last, so it wins
        index[norm_company(name)] = ticker
    return index


async def refresh_fund_holdings(db: AsyncSession, now: datetime | None = None) -> int:
    """Fetch holdings for held funds not checked in a week; returns how many were updated."""
    now = now or utcnow()
    held = select(PortfolioFund.scheme_code).distinct()
    due = (await db.execute(select(MutualFund).where(
        MutualFund.scheme_code.in_(held),
        or_(MutualFund.holdings_checked_at.is_(None), MutualFund.holdings_checked_at < now - CHECK_EVERY),
    ))).scalars().all()
    if not due:
        return 0
    index = await _ticker_index(db)
    updated = 0
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        for fund in due:
            fund.holdings_checked_at = now  # found or not, the next try is a week away
            got = await fetch_scheme(client, fund)
            if got is None:
                logger.warning(f"No Groww holdings found for fund {fund.scheme_code}")
                continue
            fund.groww_id, data = got
            as_of, rows = parse_scheme(data)
            if not rows:
                continue
            await db.execute(delete(FundHolding).where(FundHolding.scheme_code == fund.scheme_code))
            db.add_all(FundHolding(scheme_code=fund.scheme_code, ticker=index.get(norm_company(r["name"])) if r["kind"] == "equity" else None,
                                   **r) for r in rows)
            fund.holdings_as_of = as_of
            updated += 1
    await db.commit()
    if updated:
        logger.info(f"Refreshed holdings for {updated}/{len(due)} mutual funds")
    return updated
