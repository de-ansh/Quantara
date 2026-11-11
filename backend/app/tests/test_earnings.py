"""Declared results from NSE integrated filings, and the cross-company filings feed."""

from datetime import date, datetime, timedelta

import httpx
import pytest

from app.api.v1.market import parse_announcements
from app.core.clock import utcnow
from app.models.quarterly_result import QuarterlyResult
from app.models.stock import Stock
from app.services import earnings, nse_market
from app.services.earnings import growth, parse_result_xbrl, pick_filings


def _xbrl(revenue: float, profit: float) -> str:
    return f"""<xbrli:xbrl><in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-5">{revenue}</in-bse-fin:RevenueFromOperations>
<in-bse-fin:RevenueFromOperations contextRef="FourD" unitRef="INR" decimals="-5">{revenue * 2}</in-bse-fin:RevenueFromOperations>
<in-bse-fin:ProfitLossForPeriod contextRef="OneD" unitRef="INR" decimals="-5">{profit}</in-bse-fin:ProfitLossForPeriod>
<in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="OneD" unitRef="INRPerShare" decimals="2">4.5</in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations></xbrli:xbrl>"""


def _filing(qe: str, basis: str, created: str, xbrl: str) -> dict:
    return {"type": "Integrated Filing- Financials", "qe_Date": qe, "consolidated": basis, "creation_Date": created,
            "xbrl": f"https://x/{xbrl}", "pdf_attach": f"https://nsearchives.example.com/{qe}.pdf"}


def test_xbrl_reads_the_quarter_not_the_year_to_date():
    assert parse_result_xbrl(_xbrl(1000.0, 150.0)) == {"revenue": 1000.0, "profit": 150.0, "eps": 4.5}
    assert growth(120, 100) == 20.0 and growth(50, -10) is None and growth(None, 5) is None


def test_consolidated_and_newest_revision_win():
    rows = [
        _filing("30-SEP-2026", "Standalone", "08-Oct-2026 10:07:48", "s"),
        _filing("30-SEP-2026", "Consolidated", "08-Oct-2026 10:08:10", "c-old"),
        _filing("30-SEP-2026", "Consolidated", "09-Oct-2026 09:00:00", "c-new"),
        {"type": "Integrated Filing- Governance", "qe_Date": "30-SEP-2026", "xbrl": "g"},
        _filing("30-JUN-2026", "Standalone", "09-Jul-2026 06:36:12", "jun"),
    ]
    picked = pick_filings(rows)
    assert picked[date(2026, 9, 30)]["xbrl"] == "https://x/c-new" and picked[date(2026, 6, 30)]["xbrl"] == "https://x/jun"


@pytest.mark.asyncio
async def test_refresh_stores_latest_previous_and_year_ago_then_reports_growth(db_session, monkeypatch):
    db_session.add(Stock(ticker="TCS.NS", name="TCS", sector="Technology"))
    await db_session.commit()
    files = {"q-now": _xbrl(1200.0, 180.0), "q-prev": _xbrl(1100.0, 170.0), "q-ago": _xbrl(1000.0, 150.0), "q-old": _xbrl(900.0, 140.0)}
    filed = (utcnow() - timedelta(days=3)).strftime("%d-%b-%Y %H:%M:%S")

    async def listing(path: str, ttl: float = 0):
        assert path.endswith("symbol=TCS") and ttl == 0
        return {"data": [_filing("30-SEP-2026", "Consolidated", filed, "q-now"), _filing("30-JUN-2026", "Consolidated", "09-Jul-2026 06:36:12", "q-prev"),
                         _filing("30-SEP-2025", "Consolidated", "09-Oct-2025 06:36:12", "q-ago"), _filing("30-JUN-2025", "Consolidated", "09-Jul-2025 06:36:12", "q-old")]}

    async def handle(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=files[str(request.url).rsplit("/", 1)[-1]], request=request)

    monkeypatch.setattr(nse_market, "nse_json", listing)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    monkeypatch.setattr(earnings, "PAUSE_SECONDS", 0)
    assert await earnings.refresh_results(db_session) == 3  # the quarter, the one before, a year ago; not older
    assert await earnings.refresh_results(db_session) == 0  # checked within a day: skipped

    [row] = await earnings.declared_results(db_session)
    assert row["ticker"] == "TCS.NS" and row["quarter_end"] == "2026-09-30" and row["consolidated"] is True
    assert row["revenue_yoy_pct"] == 20.0 and row["profit_yoy_pct"] == 20.0
    assert row["revenue_qoq_pct"] == 9.1 and row["profit_qoq_pct"] == 5.9


@pytest.mark.asyncio
async def test_old_declarations_drop_out_of_the_tracker(db_session):
    db_session.add(Stock(ticker="OLD.NS", name="Old"))
    await db_session.flush()
    db_session.add(QuarterlyResult(ticker="OLD.NS", quarter_end=date(2026, 3, 31), consolidated=False, revenue=1, profit=1,
                                   filed_at=datetime(2026, 4, 20)))
    await db_session.commit()
    assert await earnings.declared_results(db_session, days=45) == []


def test_announcements_feed_is_newest_first_and_keeps_only_https_links():
    rows = [
        {"symbol": "A", "sm_name": "A Ltd", "desc": "Press Release", "attchmntText": "a", "sort_date": "2026-11-11 10:00:00", "attchmntFile": "https://nsearchives.nseindia.com/a.pdf"},
        {"symbol": "B", "sm_name": "B Ltd", "desc": "Updates", "attchmntText": "b", "sort_date": "2026-11-11 14:20:42", "attchmntFile": "javascript:alert(1)"},
    ]
    feed = parse_announcements(rows)
    assert [f.ticker for f in feed] == ["B.NS", "A.NS"] and feed[0].pdf_url is None and feed[1].pdf_url.endswith("a.pdf")
