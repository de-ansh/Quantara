"""Link new NSE earnings-call transcripts and recordings to tracked stocks, from the exchanges' RSS feeds.

NSE announces a call three ways:
- a transcript XBRL file carrying the NSE symbol, BSE scrip code and a transcript link (matched exactly:
  SYMBOL.NS, SYMBOL.BO, CODE.BO). That link is often the company's investor page, so the same company's
  transcript in BSE's feed (always a direct PDF) is the fallback;
- a transcript PDF attached directly, whose file name starts with the NSE symbol;
- an audio-recording XBRL file with a direct link to the call recording, filed within a day of the call,
  usually days before the transcript. Recordings cost money to transcribe, so only watched or held
  stocks get them, and only when nothing newer than the call is linked; the PDF replaces it later.
"""

import asyncio
import html
import re
from datetime import date
from typing import Any

import httpx
import sentry_sdk
from sqlalchemy import delete, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import sleep_wall, utcnow
from app.core.logging import get_logger
from app.models.portfolio import PortfolioPosition
from app.models.research import ResearchReport
from app.models.stock import Stock
from app.models.watchlist import WatchlistItem
from app.providers.filing import FilingError, fetch_filing_text

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


def _tag(name: str, text: str) -> str | None:
    """Text of the first <name> or <prefix:name> element (RSS and XBRL are both flat here)."""
    match = re.search(rf"<(?:[\w-]+:)?{name}\b[^>]*>(.*?)</(?:[\w-]+:)?{name}>", text, re.S)
    return html.unescape(match.group(1)).strip() if match else None


# NSE names attachments SYMBOL_<timestamp>_..., e.g. AUROPHARMA_11112026130442_LtrToSEsTranscript.pdf
_PDF_SYMBOL = re.compile(r"/corporate/([A-Z0-9&-]+)_\d{8,}")


def call_announcements(feed: str) -> list[tuple[str, str, str]]:
    """(kind, link, company) for transcript XBRL, transcript PDF and audio-recording items, newest first."""
    found = []
    for item in _ITEM.findall(feed):
        link, description = _tag("link", item), (_tag("description", item) or "").lower()
        company = _tag("title", item) or ""
        if not link:
            continue
        if link.endswith(".xml") and "transcript" in description:
            found.append(("transcript", link, company))
        elif link.lower().endswith(".pdf") and "transcript" in description and _PDF_SYMBOL.search(link):
            found.append(("transcript_pdf", link, company))
        elif link.endswith(".xml") and "audio recording" in description:
            found.append(("recording", link, company))
    return found


def transcript_xbrl_links(feed: str) -> list[str]:
    """XBRL links of the feed's earnings-call transcript announcements."""
    return [link for kind, link, _ in call_announcements(feed) if kind == "transcript"]


def _first_word(name: str | None) -> str:
    return (name or "").split(" ")[0].lower()


async def pdf_announcement_symbol(db: AsyncSession, link: str, company: str) -> str | None:
    """NSE symbol behind a transcript PDF's file name, or None when no tracked stock matches.

    The prefix is usually the symbol, but NSE sometimes appends digits (BSE1, INTERARCH1983); the
    digit-less form is only trusted when the stock's name starts like the announcing company's.
    """
    found = _PDF_SYMBOL.search(link)
    if not found:
        return None
    prefix = found.group(1)
    if await db.get(Stock, f"{prefix}.NS"):
        return prefix
    stripped = prefix.rstrip("0123456789")
    stock = await db.get(Stock, f"{stripped}.NS") if stripped and stripped != prefix else None
    if stock and _first_word(stock.name) == _first_word(company):
        return stripped
    return None


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


def parse_recording_xbrl(xbrl: str) -> dict | None:
    """Symbol, BSE code, recording link and call date from an audio-recording XBRL; None if it isn't one."""
    purpose = _tag("PurposeOfDisclosure", xbrl) or ""
    url = _tag("WeblinkOfAudioRecording", xbrl)
    symbol = _tag("NSESymbol", xbrl)
    if not purpose.lower().startswith("audio recording") or not url or not symbol:
        return None
    try:
        call_date = date.fromisoformat(_tag("DateOfCallForAudioRecording", xbrl) or "")
    except ValueError:
        call_date = None
    return {"symbol": symbol.upper(), "scrip_code": _tag("ScripCode", xbrl) or "", "url": url, "call_date": call_date}


async def _bse_feed(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        resp = await client.get(BSE_ANNOUNCEMENTS_RSS)
        resp.raise_for_status()
        return bse_transcript_pdfs(resp.text)
    except httpx.HTTPError as e:
        logger.warning(f"BSE announcements feed unavailable: {e}")
        return {}


async def link_new_transcripts(db: AsyncSession) -> int:
    """Attach transcripts and recordings announced since the last pass; returns how many stocks were linked."""
    linked = 0
    held: set[str] | None = None  # watched or held tickers, loaded once a recording needs them
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "Quantara/1.0"}) as client:
        feed = await client.get(NSE_ANNOUNCEMENTS_RSS)
        feed.raise_for_status()
        bse_pdfs: dict[str, str] | None = None  # fetched only once a tracked stock needs it
        for kind, xbrl_url, company in call_announcements(feed.text):
            if xbrl_url in _seen_xbrl:
                continue
            info: dict[str, Any] | None
            if kind == "transcript_pdf":
                symbol = await pdf_announcement_symbol(db, xbrl_url, company)
                info = {"symbol": symbol, "scrip_code": "", "url": xbrl_url} if symbol else None
            else:
                try:
                    resp = await client.get(xbrl_url)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    logger.warning(f"Skipping NSE XBRL {xbrl_url}: {e}")
                    continue  # not marked seen, so the next pass retries it
                info = parse_recording_xbrl(resp.text) if kind == "recording" else parse_transcript_xbrl(resp.text)
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
            if info is not None and kind == "recording" and stocks:
                if held is None:
                    held = set((await db.execute(
                        union(select(WatchlistItem.ticker), select(PortfolioPosition.ticker))
                    )).scalars().all())
                raw_date = info.get("call_date")
                call_date = raw_date if isinstance(raw_date, date) else None
                stocks = [
                    s for s in stocks
                    if s.ticker in held
                    and not (call_date and s.filing_updated_at and s.filing_updated_at.date() >= call_date)
                ]
            if info is None or not stocks:
                _seen_xbrl.add(xbrl_url)
                continue

            candidates = [info["url"]]
            if kind == "transcript":
                if bse_pdfs is None:
                    bse_pdfs = await _bse_feed(client)
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
                if kind == "recording":
                    _seen_xbrl.add(xbrl_url)  # don't re-download a big recording every pass; the transcript follows
                # Otherwise not marked seen: BSE may publish the PDF by the next pass, until NSE's feed drops the item
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
    return linked


async def run_periodic_filing_watch(interval_seconds: int = FILING_WATCH_INTERVAL_SECONDS) -> None:
    """Background loop; one worker polls at a time via an advisory lock."""
    from app.core.database import AsyncSessionLocal, run_exclusive

    async def _job() -> None:
        async with AsyncSessionLocal() as db:
            linked = await link_new_transcripts(db)
            if linked:
                logger.info(f"Linked {linked} new earnings-call transcript(s)")
            from app.services.earnings import refresh_results
            from app.services.india_signals import refresh_deals

            await refresh_results(db)
            await refresh_deals(db)  # NSE's deal files hold one day, so keep them for the deals page

    while True:
        try:
            await run_exclusive(FILING_WATCH_LOCK_ID, _job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in filing watch: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)  # no-op when Sentry is not configured
        await sleep_wall(interval_seconds)
