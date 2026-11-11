"""Keep `listed_securities` in step with the exchanges' official lists, once a day.

NSE: the equity master list and the ETF list. BSE: the latest daily bhavcopy (BSE's list API
refuses scripts); scrips also on NSE (same ISIN) are skipped so each security appears once. US:
Nasdaq Trader's list of everything traded on Nasdaq, NYSE and the other US exchanges, minus
bonds, preferreds, warrants and rights, which share their company's name but aren't its shares.
"""

import asyncio
import csv
import io
import re
from datetime import date, timedelta

import httpx
import sentry_sdk
from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.listed_security import ListedSecurity
from app.models.stock import Stock

logger = get_logger(__name__)

NSE_EQUITY_LIST = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_ETF_LIST = "https://archives.nseindia.com/content/equities/eq_etfseclist.csv"
# Always tracked (prices, fundamentals, risk), so the screener has a real universe to filter
NIFTY_500_LIST = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
BSE_BHAVCOPY = "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{day}_F_0000.CSV"
US_LIST = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
DIRECTORY_LOCK_ID = 7_301_004
DIRECTORY_REFRESH_SECONDS = 24 * 3600
_US_EXCHANGES = {"Q": "NASDAQ", "N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "Cboe", "V": "IEX"}
# Common stock and ETF symbols only; warrants/units/preferreds carry $ or other suffixes Yahoo spells differently
_US_SYMBOL = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
# shortcut: name-based, since Nasdaq Trader has no security-type column; revisit if real companies get dropped
_US_NON_EQUITY = re.compile(
    r"\bnotes? due\b|\bdebentures?\b|\bsenior notes\b|\bpreferred (stock|shares?|securities)\b"
    r"|\bpreference shares\b|\s-?\s*(rights?|warrants?)\s*$|\bwarrants? to (purchase|acquire)\b",
    re.I,
)
_US_NAME_SUFFIX = re.compile(r"\s*-?\s*(new\s+)?(common stock|common shares|ordinary shares|capital stock)\s*$", re.I)
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"}


def _rows(text: str, delimiter: str = ",") -> list[dict[str, str]]:
    """CSV rows with header names and values stripped (NSE pads its headers with spaces)."""
    return [
        {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(text), delimiter=delimiter)
    ]


def _share_kind(symbol: str) -> str:
    """Label for an Indian listing that shares its company's name but is a different security."""
    if re.search(r"-RE\d*$", symbol):
        return " (Rights Entitlement)"
    if symbol.endswith("PP"):
        return " (Partly Paid)"
    if "DVR" in symbol:
        return " (DVR)"
    if symbol.startswith("SGB"):
        return f" – {symbol}"  # exchanges cut gold-bond names before the series
    return ""


def parse_nse(text: str) -> list[dict]:
    return [
        {"ticker": f"{r['SYMBOL']}.NS", "name": r["NAME OF COMPANY"] + _share_kind(r["SYMBOL"]), "exchange": "NSE",
         "isin": r.get("ISIN NUMBER") or None, "is_etf": False}
        for r in _rows(text) if r.get("SYMBOL")
    ]


def parse_nse_etfs(text: str) -> list[dict]:
    """NSE's own ETF names are codes (NIPINDETFNIFTYBEES), so name each by symbol and what it tracks."""
    def name(r: dict[str, str]) -> str:
        what = r.get("Underlying Asset") or "ETF"
        return f"{r['Symbol']} – {what}" + ("" if re.search(r"\bETF\b|BeES", what, re.I) else " ETF")

    return [
        {"ticker": f"{r['Symbol']}.NS", "name": name(r)[:255], "exchange": "NSE",
         "isin": r.get("ISINNumber") or None, "is_etf": True}
        for r in _rows(text) if r.get("Symbol")
    ]


def parse_bse(text: str, nse_isins: set[str]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in _rows(text):
        if r.get("FinInstrmTp") != "STK" or not r.get("TckrSymb") or r.get("ISIN") in nse_isins:
            continue
        ticker, name = f"{r['TckrSymb']}.BO", r["FinInstrmNm"]
        # BSE names an ETF by its fund house only ("Mirae Asset Mutual Fund"), so lead with the symbol
        fund = "mutual fund" in name.lower()
        name = f"{r['TckrSymb']} – {name}" if fund else name + _share_kind(r["TckrSymb"])
        out[ticker] = {"ticker": ticker, "name": name, "exchange": "BSE",
                       "isin": r.get("ISIN") or None, "is_etf": fund}
    return list(out.values())


def parse_us(text: str) -> list[dict]:
    out = []
    for r in _rows(text, delimiter="|"):
        symbol = r.get("Symbol", "")
        if r.get("Test Issue") != "N" or not _US_SYMBOL.match(symbol):
            continue  # also drops the trailing "File Creation Time" line
        if _US_NON_EQUITY.search(r["Security Name"]):
            continue
        name = _US_NAME_SUFFIX.sub("", r["Security Name"]).strip()
        # Share classes often carry identical names (BRK.A / BRK.B), so name the class
        if "." in symbol and "class" not in name.lower():
            name = f"{name} Class {symbol.split('.')[1]}"
        out.append({"ticker": symbol.replace(".", "-"), "name": name[:255],
                    "exchange": _US_EXCHANGES.get(r.get("Listing Exchange", ""), "US"),
                    "isin": None, "is_etf": r.get("ETF") == "Y"})
    return out


def parse_bse_prices(text: str) -> dict[str, dict]:
    """ISIN -> end-of-day close, previous close and trade date, for every scrip in the bhavcopy."""
    out = {}
    for r in _rows(text):
        try:
            close, prev = float(r["ClsPric"]), float(r.get("PrvsClsgPric") or 0) or None
            out[r["ISIN"]] = {"close": close, "prev_close": prev, "price_date": date.fromisoformat(r["TradDt"])}
        except (KeyError, ValueError):
            continue
    return out


def parse_index_members(text: str) -> list[dict]:
    # NSE's index files can hold DUMMY* placeholders (DUMMYHEG) that never trade
    return [{"ticker": f"{r['Symbol']}.NS", "name": r.get("Company Name") or r["Symbol"]}
            for r in _rows(text) if r.get("Symbol") and not r["Symbol"].startswith("DUMMY")]


async def track_index_members(db: AsyncSession, text: str) -> int:
    """Start tracking index members not tracked yet; returns how many were added."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    members = parse_index_members(text)
    if not members:
        return 0
    added = await db.execute(
        pg_insert(Stock).values(members).on_conflict_do_nothing(index_elements=["ticker"]).returning(Stock.ticker)
    )
    return len(added.all())


async def _get(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        logger.warning(f"Directory download failed for {url}: {e}")
        return None


async def _latest_bhavcopy(client: httpx.AsyncClient, today: date) -> str | None:
    """BSE publishes one file per trading day; walk back over weekends and holidays."""
    for back in range(8):
        day = (today - timedelta(days=back)).strftime("%Y%m%d")
        try:
            resp = await client.get(BSE_BHAVCOPY.format(day=day))
        except httpx.HTTPError as e:
            logger.warning(f"BSE bhavcopy download failed: {e}")
            return None
        if resp.status_code == 200 and resp.text.startswith("TradDt"):
            return resp.text
    return None


async def _replace(db: AsyncSession, rows: list[dict], exchanges: list[str]) -> None:
    await db.execute(delete(ListedSecurity).where(ListedSecurity.exchange.in_(exchanges)))
    if rows:
        now = utcnow()
        no_price = {"close": None, "prev_close": None, "price_date": None}  # bulk insert needs one key set
        await db.execute(insert(ListedSecurity), [{**no_price, **r, "updated_at": now} for r in rows])


async def refresh_directory(db: AsyncSession) -> dict[str, int]:
    """Re-load each market whose list downloaded; a failed source keeps yesterday's rows."""
    counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=60.0, headers=_HEADERS, follow_redirects=True) as client:
        nse_text, etf_text, bse_text, us_text, nifty500_text = await asyncio.gather(
            _get(client, NSE_EQUITY_LIST), _get(client, NSE_ETF_LIST),
            _latest_bhavcopy(client, date.today()), _get(client, US_LIST), _get(client, NIFTY_500_LIST),
        )
    # Shares and ETFs replace NSE rows together, so a failed ETF list doesn't wipe yesterday's ETFs
    nse = parse_nse(nse_text) + parse_nse_etfs(etf_text) if nse_text and etf_text else []
    # One price file for both Indian exchanges: an NSE company's BSE close, matched by ISIN
    prices = parse_bse_prices(bse_text) if bse_text else {}
    for row in nse:
        row.update(prices.get(row["isin"] or "", {}))
    if nse:
        await _replace(db, nse, ["NSE"])
        counts["NSE"] = len(nse)
    # Without a fresh NSE list the ISIN dedupe can't run, so BSE waits for the next pass
    bse = parse_bse(bse_text, {r["isin"] for r in nse if r["isin"]}) if bse_text and nse else []
    for row in bse:
        row.update(prices.get(row["isin"] or "", {}))
    if bse:
        await _replace(db, bse, ["BSE"])
        counts["BSE"] = len(bse)
    us = parse_us(us_text) if us_text else []
    if us:
        await _replace(db, us, sorted({*_US_EXCHANGES.values(), "US"}))
        counts["US"] = len(us)
    if nifty500_text:
        counts["newly_tracked"] = await track_index_members(db, nifty500_text)
    # Stocks tracked before they had a name (saved as the bare ticker) take the exchange's name
    listed_name = select(ListedSecurity.name).where(ListedSecurity.ticker == Stock.ticker).scalar_subquery()
    await db.execute(
        update(Stock)
        .where(or_(Stock.name.is_(None), Stock.name == Stock.ticker), listed_name.is_not(None))
        .values(name=listed_name)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return counts


async def run_periodic_directory_refresh(interval_seconds: int = DIRECTORY_REFRESH_SECONDS) -> None:
    """Background loop; one worker refreshes at a time via an advisory lock."""
    from app.core.database import AsyncSessionLocal, run_exclusive

    async def _job() -> None:
        async with AsyncSessionLocal() as db:
            newest = (await db.execute(select(func.max(ListedSecurity.updated_at)))).scalar()
            if newest and utcnow() - newest < timedelta(seconds=interval_seconds):
                return  # a restart within the day reuses the lists already loaded
            logger.info(f"Stock directory refreshed: {await refresh_directory(db)}")
            from app.services.shareholding import refresh_shareholding

            # Daily too: shareholding is filed quarterly, and the history fills in 50 stocks a run
            logger.info(f"Promoter holding changes signalled: {await refresh_shareholding(db)}")
            from app.services.event_alerts import notify_upcoming_events

            await notify_upcoming_events(db)

    while True:
        try:
            await run_exclusive(DIRECTORY_LOCK_ID, _job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in stock directory refresh: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)  # no-op when Sentry is not configured
        await asyncio.sleep(interval_seconds)
