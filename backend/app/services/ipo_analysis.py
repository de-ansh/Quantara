"""IPO analysis: NSE issue data plus the prospectus's key sections, read by the LLM into pros, cons and a call.

NSE's issue page gives the terms (price band, lot, fresh issue vs offer for sale) and live
subscription by investor type; the red herring prospectus (RHP) gives the business, financials and
the company's own basis for the price. Only the sections that matter are sent to the model.
"""

import asyncio
import io
import json
import re
import zipfile
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI, OpenAIError
from pypdf import PdfReader

from app.core.config import settings
from app.core.logging import get_logger
from app.services import nse_market

logger = get_logger(__name__)

DETAIL_PATH = "api/ipo-detail?symbol={symbol}&series={series}"
DETAIL_TTL = 30 * 60.0  # subscription moves through the bidding days
MAX_RHP_BYTES = 80 * 1024 * 1024
SECTION_PAGES = 4
MAX_SECTION_CHARS = 45_000  # about 11k tokens of prospectus per analysis
RECOMMENDATIONS = ("Apply", "Apply for listing gains", "Avoid")
_SECTIONS = {
    "Offer summary": r"SUMMARY OF (?:THE )?(?:OFFER|ISSUE|RED HERRING|DRAFT RED HERRING)?\s*(?:DOCUMENT|PROSPECTUS)",
    "Objects of the offer": r"OBJECTS OF THE (?:OFFER|ISSUE)",
    "Financial summary": r"SUMMARY OF (?:RESTATED |CONSOLIDATED )*FINANCIAL (?:INFORMATION|STATEMENTS)",
    "Basis for the price": r"BASIS FOR (?:THE )?(?:OFFER|ISSUE) PRICE",
    "Risk factors": r"^\s*RISK FACTORS\s*$",
}
_AMOUNT = r"(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d+)?)\s*(million|crore|lakh)"
_SHARES = r"([\d,]+)\s*(?:Equity\s+)?Shares"
_CRORE = {"million": 0.1, "crore": 1.0, "lakh": 0.01}


def _num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _part(text: str, label: str) -> tuple[float | None, float | None]:
    """(crore, shares) mentioned right after `label` in the issue-size sentence."""
    m = re.search(label + r"(.{0,160})", text, re.I | re.S)
    if not m:
        return None, None
    after = re.split(r"\band\b(?=\s+(?:an\s+)?(?:offer|fresh))", m.group(1), maxsplit=1, flags=re.I)[0]
    amount = re.search(_AMOUNT, after, re.I)
    shares = re.search(_SHARES, after, re.I)
    value = _num(amount.group(1)) if amount else None
    crore = value * _CRORE[amount.group(2).lower()] if amount and value is not None else None
    return crore, _num(shares.group(1)) if shares else None


def parse_issue(detail: dict) -> dict:
    """Terms, the fresh / offer-for-sale split and subscription from NSE's ipo-detail response."""
    info = {str(r.get("title")): str(r.get("value") or "").strip('" ') for r in (detail.get("issueInfo") or {}).get("dataList", []) if r.get("title")}
    meta = detail.get("metaInfo") or {}
    size = info.get("Issue Size", "")
    fresh_cr, fresh_sh = _part(size, r"Fresh Issue")
    ofs_cr, ofs_sh = _part(size, r"Offer for Sale")
    # The share of the issue that is existing holders selling, in whichever unit both parts use
    if fresh_cr is not None or ofs_cr is not None:
        ofs_share = (ofs_cr or 0) / ((fresh_cr or 0) + (ofs_cr or 0)) if (fresh_cr or ofs_cr) else None
    elif fresh_sh is not None or ofs_sh is not None:
        ofs_share = (ofs_sh or 0) / ((fresh_sh or 0) + (ofs_sh or 0)) if (fresh_sh or ofs_sh) else None
    else:
        ofs_share = None

    subscription: dict[str, float] = {}
    for row in (detail.get("activeCat") or {}).get("dataList", [])[1:]:
        category, times = str(row.get("category") or ""), _num(row.get("noOfTotalMeant"))
        if times is None:
            continue
        for key, word in (("qib", "Qualified Institutional"), ("nii", "Non Institutional Investors"), ("retail", "Retail Individual"),
                          ("employee", "Employee"), ("total", "Total")):
            if category.startswith(word) and key not in subscription:
                subscription[key] = round(times, 2)
    if not subscription.get("total"):
        subscription = {}  # SME issues can report zeros even after listing: no data, not no demand

    return {
        "symbol": meta.get("symbol"),
        "company": detail.get("companyName") or meta.get("companyName"),
        "industry": meta.get("industry"),
        "segment": meta.get("segment"),
        "period": info.get("Issue Period"),
        "price_range": info.get("Price Range"),
        "lot": info.get("Bid Lot"),
        "issue_size": size,
        "fresh_issue_crore": round(fresh_cr, 2) if fresh_cr is not None else None,
        "offer_for_sale_crore": round(ofs_cr, 2) if ofs_cr is not None else None,
        "offer_for_sale_share": round(ofs_share, 3) if ofs_share is not None else None,
        "subscription": subscription,
        "rhp_url": info.get("Red Herring Prospectus"),
    }


def issue_pros_cons(issue: dict) -> tuple[list[str], list[str]]:
    """What the issue terms and demand alone say, before reading the prospectus."""
    pros, cons = [], []
    sub = issue["subscription"]
    if (qib := sub.get("qib")) is not None:
        if qib >= 10:
            pros.append(f"Institutions bid {qib:.1f}x their quota")
        elif qib < 1:
            cons.append(f"Weak institutional demand ({qib:.2f}x the QIB quota)")
    if (total := sub.get("total")) is not None:
        if total >= 20:
            pros.append(f"Heavily subscribed overall ({total:.1f}x)")
        elif total < 1:
            cons.append(f"Undersubscribed so far ({total:.2f}x)")
    share = issue["offer_for_sale_share"]
    if share is not None:
        if share == 0:
            pros.append("All the money raised goes to the company; no existing holder is selling")
        elif share >= 0.5:
            cons.append(f"{share:.0%} of the issue is existing shareholders selling; that money doesn't reach the company")
    if (issue.get("segment") or "").upper() == "SME":
        cons.append("SME platform: thinner trading and large minimum lots make it harder to exit")
    return pros, cons


def rhp_sections(pages: list[str]) -> str:
    """The prospectus sections worth reading, from page texts; table-of-contents hits are skipped."""
    chunks = []
    for title, pattern in _SECTIONS.items():
        start = next((i for i, text in enumerate(pages) if i > 5 and re.search(pattern, text[:400], re.M)), None)
        if start is not None:
            body = " ".join(" ".join(pages[start:start + SECTION_PAGES]).split())
            chunks.append(f"## {title}\n{body[:MAX_SECTION_CHARS // len(_SECTIONS)]}")
    return "\n\n".join(chunks)


def _pdf_pages(data: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]


async def fetch_rhp_sections(url: str | None) -> str:
    """Key sections of the RHP NSE links (a zip holding the PDF); empty when it can't be read."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith("nseindia.com"):
        return ""  # only NSE's own archive, never a link from elsewhere
    try:
        async with httpx.AsyncClient(timeout=120, headers={"User-Agent": "Mozilla/5.0", "Referer": nse_market.BASE}) as client:
            resp = await client.get(url or "")
            resp.raise_for_status()
        if len(resp.content) > MAX_RHP_BYTES:
            return ""
        data = resp.content
        if data[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                pdfs = sorted((i for i in z.infolist() if i.filename.lower().endswith(".pdf")), key=lambda i: -i.file_size)
                rhp = next((i for i in pdfs if "rhp" in i.filename.lower()), pdfs[0] if pdfs else None)
                if rhp is None or rhp.file_size > MAX_RHP_BYTES:
                    return ""
                data = z.read(rhp)
        return rhp_sections(await asyncio.to_thread(_pdf_pages, data))
    except (httpx.HTTPError, zipfile.BadZipFile, ValueError, OSError) as e:
        logger.warning(f"RHP unreadable ({url}): {e}")
        return ""


_PROMPT = """You are an equity analyst assessing an Indian IPO for a retail investor.
Use only the data given. Do not invent numbers. If something isn't in the data, say so.
Weigh: business quality and growth, profitability, valuation at the upper price band against listed
peers (from the basis-for-price section), what the money is used for, how much is existing holders
selling, demand by investor type, and the main risks.
The prospectus often prints the price as [●]; when the latest EPS is in the data, compute the P/E at
the upper end of the price band (upper price / EPS) yourself and compare it with the peers' P/E.

Return JSON:
{
  "summary": "2-3 sentences on what the company does and the overall view",
  "financials": "1-2 sentences on revenue, profit and margins over the years given",
  "valuation": "1-2 sentences on the price versus earnings and peers",
  "pros": ["specific, with numbers where the data has them"],
  "cons": ["specific, with numbers where the data has them"],
  "recommendation": "Apply" | "Apply for listing gains" | "Avoid",
  "reasoning": "1-2 sentences tying the call to the pros and cons",
  "confidence": 0-100
}
"Apply" means worth holding for the long term; "Apply for listing gains" means demand or pricing
looks favourable for listing day but the long-term case is weak; "Avoid" otherwise."""


async def llm_analysis(issue: dict, sections: str) -> dict:
    facts = {k: v for k, v in issue.items() if k != "rhp_url"}
    user = f"Issue data (from NSE):\n{json.dumps(facts, ensure_ascii=False)}\n\nProspectus sections:\n{sections or '(the prospectus could not be read)'}"
    try:
        resp = await AsyncOpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": user}],
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (OpenAIError, json.JSONDecodeError) as e:
        raise RuntimeError("The AI analysis is unavailable right now") from e


def _merge(first: list[str], second: Any) -> list[str]:
    out = list(first)
    for item in second if isinstance(second, list) else []:
        if isinstance(item, str) and item.strip() and item not in out:
            out.append(item.strip())
    return out[:8]


async def analyze_ipo(symbol: str, series: str) -> dict:
    """Full analysis; raises LookupError when NSE has no such issue, RuntimeError when the AI fails."""
    detail = await nse_market.nse_json(DETAIL_PATH.format(symbol=symbol, series=series), DETAIL_TTL)
    if not isinstance(detail, dict) or not detail.get("issueInfo"):
        raise LookupError(f"NSE has no IPO details for {symbol}")
    issue = parse_issue(detail)
    sections = await fetch_rhp_sections(issue["rhp_url"])
    ai = await llm_analysis(issue, sections)
    rule_pros, rule_cons = issue_pros_cons(issue)
    recommendation = ai.get("recommendation") if ai.get("recommendation") in RECOMMENDATIONS else None
    confidence = _num(ai.get("confidence"))
    return {
        "issue": issue,
        "summary": str(ai.get("summary") or ""),
        "financials": str(ai.get("financials") or ""),
        "valuation": str(ai.get("valuation") or ""),
        "pros": _merge(rule_pros, ai.get("pros")),
        "cons": _merge(rule_cons, ai.get("cons")),
        "recommendation": recommendation,
        "reasoning": str(ai.get("reasoning") or ""),
        "confidence": max(0.0, min(100.0, confidence)) if confidence is not None else None,
        "read_prospectus": bool(sections),
    }
