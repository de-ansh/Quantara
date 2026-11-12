"""Concall monitor (NSE call announcements + AI summary) and stored bulk/block deals."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from app.core.config import settings
from app.models.large_deal import LargeDeal
from app.services import concalls, nse_market
from app.services.concalls import call_kind, parse_concalls
from app.services.india_signals import deal_rows, store_deals

CAT = concalls.CALL_CATEGORY
TODAY = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
LONG_TRANSCRIPT = "Moderator: good evening. " * 400


def _row(symbol, text, when=f"{TODAY} 11:20:33", desc=CAT, link=None):
    return {"symbol": symbol, "sm_name": f"{symbol} Ltd", "desc": desc, "attchmntText": text, "sort_date": when,
            "attchmntFile": link or f"https://nsearchives.nseindia.com/corporate/{symbol}_1.pdf"}


@pytest.mark.parametrize("text,kind", [
    ("has informed the Exchange about Transcript of earnings call -Q2 FY 2026-27", "transcript"),
    ("has informed the Exchange about audio recording of the earnings call", "recording"),
    ("has informed the Exchange about Schedule of meet", "schedule"),
    ("has informed the Exchange about Updates", None),
])
def test_call_kind(text, kind):
    assert call_kind(text) == kind


def test_parse_concalls_keeps_call_category_newest_first():
    rows = [
        _row("OLD", "Transcript", when="2026-11-01 10:00:00"),
        _row("NEW", "Schedule of meet"),
        _row("RES", "Financial results", desc="Outcome of Board Meeting"),
        _row("UPD", "Updates"),
        _row("BAD", "Transcript", link="ftp://x"),
    ]
    out = parse_concalls(rows)
    assert [c["ticker"] for c in out] == ["NEW.NS", "BAD.NS", "OLD.NS"]
    assert out[0]["kind"] == "schedule" and out[1]["pdf_url"] is None


def test_deal_rows_parse_both_files():
    bulk = ("Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price,Remarks\n"
            "11-NOV-2026,AAATECH,AAA Technologies Limited,VAIBHAV DOSHI,BUY,\"66,829\",93.89,-\n"
            "11-NOV-2026,BAD,Bad,X,HOLD,10,1,-\n")
    rows = deal_rows(bulk, "bulk")
    assert rows == [{"deal_date": date(2026, 11, 11), "kind": "bulk", "symbol": "AAATECH", "company": "AAA Technologies Limited",
                     "client": "VAIBHAV DOSHI", "side": "BUY", "quantity": 66829.0, "price": 93.89}]


@pytest.mark.asyncio
async def test_deals_are_stored_once_and_listed_largest_first(client, db_session):
    block = ("Date,Symbol,Security Name,Client Name,Buy/Sell,Quantity Traded,Trade Price / Wght. Avg. Price\n"
             f"{datetime.now(ZoneInfo('Asia/Kolkata')):%d-%b-%Y},SMALL,Small Ltd,FUND A,BUY,100,10\n"
             f"{datetime.now(ZoneInfo('Asia/Kolkata')):%d-%b-%Y},BIG,Big Ltd,FUND B,SELL,1000,500\n")
    assert await store_deals(db_session, None, block) == 2
    await store_deals(db_session, None, block)  # the hourly re-read adds nothing
    assert (await db_session.execute(select(func.count()).select_from(LargeDeal))).scalar() == 2

    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    resp = await client.get("/api/v1/market/deals", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [d["ticker"] for d in body] == ["BIG.NS", "SMALL.NS"]
    assert body[0]["value"] == 500_000 and body[0]["kind"] == "block" and body[0]["side"] == "SELL"


@pytest.mark.asyncio
async def test_summary_uses_the_feeds_newest_transcript_and_caches(client, monkeypatch):
    feed = [_row("ACME", "Transcript of earnings call"), _row("ACME", "Transcript", when="2026-10-20 10:00:00",
            link="https://nsearchives.nseindia.com/corporate/ACME_old.pdf"), _row("ACME", "Schedule of meet")]
    calls = {"llm": 0, "url": None}

    async def nse(path, ttl=0):
        return feed

    async def text(url, follow_page=True):
        calls["url"] = url
        return LONG_TRANSCRIPT

    async def llm(transcript):
        calls["llm"] += 1
        return {"quarter": "Q2 FY27", "tone": "Positive", "summary": "Good quarter.", "guidance": "15% growth.",
                "highlights": ["Revenue +12%"], "concerns": []}

    monkeypatch.setattr(nse_market, "nse_json", nse)
    monkeypatch.setattr(concalls, "fetch_filing_text", text)
    monkeypatch.setattr(concalls, "summarize_transcript", llm)
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = await client.get("/api/v1/market/concalls", params={"days": 1}, headers=headers)
    assert [c["kind"] for c in listed.json()] == ["transcript", "schedule"]  # the October one is outside a day

    redis = Redis.from_url(settings.redis_url)
    for key in await redis.keys("concall-summary:*"):
        await redis.delete(key)
    try:
        first = await client.get("/api/v1/market/concalls/acme.ns/summary", headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["tone"] == "Positive" and calls["url"].endswith("ACME_1.pdf")
        again = await client.get("/api/v1/market/concalls/ACME/summary", headers=headers)
        assert again.json()["cached"] is True and calls["llm"] == 1
        assert (await client.get("/api/v1/market/concalls/NOPE/summary", headers=headers)).status_code == 404
    finally:
        for key in await redis.keys("concall-summary:*"):
            await redis.delete(key)
        await redis.aclose()


@pytest.mark.asyncio
async def test_cover_letter_is_not_summarised(monkeypatch):
    async def text(url, follow_page=True):
        return "Please find the transcript on our website."

    monkeypatch.setattr(concalls, "fetch_filing_text", text)
    with pytest.raises(LookupError, match="cover letter"):
        await concalls.summarize_call({"pdf_url": "https://nsearchives.nseindia.com/x.pdf"})
