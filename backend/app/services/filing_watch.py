"""Link new NSE earnings-call transcripts to tracked stocks, from the exchanges' official RSS feeds.

Each NSE transcript announcement points to a small XBRL file carrying the NSE symbol, the BSE scrip
code and a link to the transcript, so stocks are matched exactly (SYMBOL.NS, SYMBOL.BO, CODE.BO).
That link is often the company's investor page rather than the PDF, so the same company's
transcript filing in BSE's feed (always a direct PDF) is the fallback.
"""

import asyncio
import html
import re

import httpx
import sentry_sdk
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.research import ResearchReport
from app.models.stock import Stock
from app.providers.filing import FilingError, fetch_filing_text
from app.services.notify import notify_slack

logger = get_logger(__name__)

NSE_ANNOUNCEMENTS_RSS = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
BSE_ANNOUNCEMENTS_RSS = "https://www.bseindia.com/data/xml/announcements.xml"
FILING_WATCH_LOCK_ID = 7_301_003
FILING_WATCH_INTERVAL_SECONDS = 30 * 60
# Shorter "transcripts" are cover letters that only link to the company website
TRANSCRIPT_MIN_CHARS = 5_000

_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_BSE_TRANSCRIPT = re.compile(r"transcript|conference call|earnings? call", re.I)
# shortcut: in-memory, so a restart re-reads the XBRL files still in the feed once; persist if that gets costly
_seen_xbrl: set[str] = set()
_reported_unreadable: set[str] = set()


def _tag(name: str, text: str) -> str | None:
    """Text of the first <name> or <prefix:name> element (RSS and XBRL are both flat here)."""
    match = re.search(rf"<(?:[\w-]+:)?{name}\b[^>]*>(.*?)</(?:[\w-]+:)?{name}>", text, re.S)
    return html.unescape(match.group(1)).strip() if match else None


def transcript_xbrl_links(feed: str) -> list[str]:
    """XBRL links of the feed's earnings-call transcript announcements."""
    links = []
    for item in _ITEM.findall(feed):
        link, description = _tag("link", item), _tag("description", item) or ""
        # Transcript items without an XBRL file can't be matched to a symbol, so they're skipped
        if link and link.endswith(".xml") and "transcript" in description.lower():
            links.append(link)
    return links


def bse_transcript_pdfs(feed: str) -> dict[str, str]:
    """BSE scrip code -> PDF of its newest transcript filing in BSE's announcements feed."""
    pdfs: dict[str, str] = {}
    for item in _ITEM.findall(feed):
        code, link = _tag("scripcode", item), _tag("link", item)
        if code and link and link.lower().endswith(".pdf") and _BSE_TRANSCRIPT.search(_tag("description", item) or ""):
            pdfs.setdefault(code, link)  # the feed is newest first
    return pdfs


def parse_transcript_xbrl(xbrl: str) -> dict[str, str] | None:
    """Symbol, BSE code and PDF link from a transcript announcement's XBRL; None if it isn't one."""
    purpose = _tag("PurposeOfDisclosure", xbrl) or ""
    pdf = _tag("WeblinkOfTranscripts", xbrl)
    symbol = _tag("NSESymbol", xbrl)
    if not purpose.lower().startswith("transcript") or not pdf or not symbol:
        return None
    return {"symbol": symbol.upper(), "scrip_code": _tag("ScripCode", xbrl) or "", "url": pdf}


async def _bse_feed(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        resp = await client.get(BSE_ANNOUNCEMENTS_RSS)
        resp.raise_for_status()
        return bse_transcript_pdfs(resp.text)
    except httpx.HTTPError as e:
        logger.warning(f"BSE announcements feed unavailable: {e}")
        return {}


async def link_new_transcripts(db: AsyncSession) -> int:
    """Attach transcripts announced since the last pass to matching stocks; returns how many were linked."""
    linked = 0
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "Quantara/1.0"}) as client:
        feed = await client.get(NSE_ANNOUNCEMENTS_RSS)
        feed.raise_for_status()
        bse_pdfs: dict[str, str] | None = None  # fetched only once a tracked stock needs it
        for xbrl_url in transcript_xbrl_links(feed.text):
            if xbrl_url in _seen_xbrl:
                continue
            try:
                resp = await client.get(xbrl_url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning(f"Skipping transcript XBRL {xbrl_url}: {e}")
                continue  # not marked seen, so the next pass retries it
            info = parse_transcript_xbrl(resp.text)
            tickers: set[str] = set()
            if info:
                tickers = {f"{info['symbol']}.NS", f"{info['symbol']}.BO"}
                if info["scrip_code"]:
                    tickers.add(f"{info['scrip_code']}.BO")
            stocks = (
                (await db.execute(select(Stock).where(Stock.ticker.in_(tickers)))).scalars().all()
                if tickers
                else []
            )
            if info is None or not stocks:
                _seen_xbrl.add(xbrl_url)
                continue

            if bse_pdfs is None:
                bse_pdfs = await _bse_feed(client)
            candidates = [info["url"]]
            if info["scrip_code"] in bse_pdfs:
                candidates.append(bse_pdfs[info["scrip_code"]])
            url = text = None
            for candidate in candidates:
                try:
                    text = await fetch_filing_text(candidate)
                    if len(text) < TRANSCRIPT_MIN_CHARS:
                        raise FilingError("only a cover letter")
                    url = candidate
                    break
                except FilingError as e:
                    logger.info(f"{info['symbol']} transcript candidate unreadable ({e}): {candidate}")
            if url is None or text is None:
                # Not marked seen: BSE may publish the PDF by the next pass, until NSE's feed drops the item
                if xbrl_url not in _reported_unreadable:
                    _reported_unreadable.add(xbrl_url)
                    await notify_slack(
                        f"New {info['symbol']} earnings-call transcript, but no readable PDF yet. "
                        f"Quantara will keep checking; or paste a PDF link on the stock page: {info['url']}"
                    )
                continue
            _seen_xbrl.add(xbrl_url)

            stocks = [s for s in stocks if s.filing_url != url]
            if not stocks:
                continue
            for stock in stocks:
                stock.filing_url = url
                stock.filing_text = text
                stock.filing_updated_at = utcnow()
            # Drop cached reports so the next view regenerates them with the transcript
            await db.execute(
                delete(ResearchReport).where(ResearchReport.ticker.in_([s.ticker for s in stocks]))
            )
            await db.commit()
            linked += len(stocks)
            await notify_slack(
                f"New earnings-call transcript linked for {', '.join(s.ticker for s in stocks)}: {url}"
            )
    return linked


async def run_periodic_filing_watch(interval_seconds: int = FILING_WATCH_INTERVAL_SECONDS) -> None:
    """Background loop; one worker polls at a time via an advisory lock."""
    from app.core.database import AsyncSessionLocal, run_exclusive

    async def _job() -> None:
        async with AsyncSessionLocal() as db:
            linked = await link_new_transcripts(db)
            if linked:
                logger.info(f"Linked {linked} new earnings-call transcript(s)")

    while True:
        try:
            await run_exclusive(FILING_WATCH_LOCK_ID, _job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in filing watch: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)  # no-op when Sentry is not configured
        await asyncio.sleep(interval_seconds)
