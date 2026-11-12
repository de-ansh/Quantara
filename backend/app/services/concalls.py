"""Earnings calls across every NSE company: schedules, recordings and transcripts, with an AI summary on demand.

NSE files all of them under one announcement category; the attachment text says which it is.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.providers.filing import FilingError, fetch_filing_text
from app.services import nse_market

CALL_CATEGORY = "Analysts/Institutional Investor Meet/Con. Call Updates"
WINDOW_DAYS = 30  # one cached fetch (~17k announcements, ~3 s) serves every period on the page
FEED_TTL = 600
MAX_TRANSCRIPT_CHARS = 80_000  # a long call is ~40k; more is appendices
MIN_TRANSCRIPT_CHARS = 5_000  # shorter "transcripts" are cover letters linking to the company site
TONES = ("Positive", "Neutral", "Cautious")

_KINDS = (
    ("transcript", re.compile(r"transcript", re.I)),
    ("recording", re.compile(r"audio|video|recording", re.I)),
    ("schedule", re.compile(r"schedule|intimation|meet", re.I)),
)


def call_kind(text: str) -> str | None:
    return next((kind for kind, pattern in _KINDS if pattern.search(text)), None)


def parse_concalls(rows: list[dict]) -> list[dict]:
    """Call announcements, newest first; other categories and unclassifiable updates are dropped."""
    out = []
    for r in rows:
        if r.get("desc") != CALL_CATEGORY or not r.get("symbol"):
            continue
        text = r.get("attchmntText") or ""
        kind = call_kind(text)
        if kind is None:
            continue
        link = str(r.get("attchmntFile") or "")
        out.append({
            "ticker": f"{r['symbol']}.NS", "company": r.get("sm_name"), "kind": kind, "summary": text or None,
            "filed_at": str(r.get("sort_date") or r.get("an_dt") or "") or None,
            "pdf_url": link if link.startswith("https://") else None,
        })
    return sorted(out, key=lambda c: c["filed_at"] or "", reverse=True)


async def recent_concalls(days: int) -> list[dict] | None:
    """Calls filed in the last `days` (at most WINDOW_DAYS); None when NSE is unavailable."""
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    path = f"api/corporate-announcements?index=equities&from_date={start:%d-%m-%Y}&to_date={today:%d-%m-%Y}"
    data = await nse_market.nse_json(path, ttl=FEED_TTL)
    rows = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
    if not isinstance(rows, list):
        return None
    cutoff = f"{today - timedelta(days=days - 1):%Y-%m-%d}"
    return [c for c in parse_concalls(rows) if (c["filed_at"] or "") >= cutoff]


_PROMPT = """You summarise an Indian listed company's earnings-call transcript for a retail investor.
Use only the transcript. Reply as JSON with keys:
"quarter" (e.g. "Q2 FY27", or "" if unclear),
"tone" (one of "Positive", "Neutral", "Cautious": management's outlook, not the share price),
"summary" (3-4 plain sentences: what happened this quarter and what management expects),
"guidance" (one or two sentences on any revenue, margin, capex or growth guidance; "" if none was given),
"highlights" (up to 5 short points, with numbers where the call gave them),
"concerns" (up to 5 short points: risks, weak segments, analyst pushback, hedged answers)."""


async def summarize_transcript(text: str) -> dict[str, Any]:
    try:
        resp = await AsyncOpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": text[:MAX_TRANSCRIPT_CHARS]}],
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except (OpenAIError, json.JSONDecodeError) as e:
        raise RuntimeError("The AI summary is unavailable right now") from e
    if not isinstance(parsed, dict):
        parsed = {}

    def points(key: str) -> list[str]:
        value = parsed.get(key)
        return [p.strip() for p in value if isinstance(p, str) and p.strip()][:5] if isinstance(value, list) else []

    return {
        "quarter": str(parsed.get("quarter") or ""),
        "tone": parsed.get("tone") if parsed.get("tone") in TONES else None,
        "summary": str(parsed.get("summary") or ""),
        "guidance": str(parsed.get("guidance") or ""),
        "highlights": points("highlights"),
        "concerns": points("concerns"),
    }


async def latest_transcript(symbol: str) -> dict | None:
    """The symbol's newest transcript announcement in the window, from NSE's own feed (never a user URL)."""
    calls = await recent_concalls(WINDOW_DAYS)
    if calls is None:
        raise RuntimeError("NSE announcements are unavailable right now")
    return next((c for c in calls if c["ticker"] == f"{symbol}.NS" and c["kind"] == "transcript" and c["pdf_url"]), None)


async def summarize_call(call: dict) -> dict[str, Any]:
    """Summary of one transcript announcement; LookupError when its PDF can't be read or is only a cover letter."""
    try:
        text = await fetch_filing_text(call["pdf_url"], follow_page=False)
    except FilingError as e:
        raise LookupError(f"The transcript PDF could not be read: {e}") from e
    if len(text) < MIN_TRANSCRIPT_CHARS:
        raise LookupError("This filing is a cover letter that links to the company's website, not the transcript")
    return {**call, **await summarize_transcript(text)}
