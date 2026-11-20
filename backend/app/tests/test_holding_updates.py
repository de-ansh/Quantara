"""Tests for the dashboard's per-holding updates feed."""

from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.clock import utcnow
from app.models.price_alert import PriceAlert
from app.models.quarterly_result import QuarterlyResult
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.models.verdict_snapshot import VerdictSnapshot
from app.services import nse_market, price_service
from app.services.holding_updates import results_text, signal_text, upcoming_events


async def _headers(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_signals_in_words():
    assert signal_text("large_deal", {"direction": "bearish", "net_pct_of_company": -1.5}) == (
        "Bulk/block deals: net selling of 1.50% of the company", "bad")
    assert signal_text("promoter_pledge", {"direction": "bearish", "pledged_pct_of_promoter": 40.68})[0] == (
        "Promoters have pledged 40.7% of their shares")
    assert signal_text("promoter_holding_change", {"direction": "bullish", "change_pp": 2.34}) == (
        "Promoter stake up 2.34 points this quarter", "good")
    assert signal_text("insider_buying", None) == ("Insider buying", "neutral")


def test_results_compare_with_a_year_ago():
    now = QuarterlyResult(ticker="X.NS", quarter_end=date(2026, 9, 30), consolidated=True, profit=1.2e9)
    before = QuarterlyResult(ticker="X.NS", quarter_end=date(2025, 9, 30), consolidated=True, profit=1.0e9)
    assert results_text(now, before) == ("Results for the quarter to 30 Sep 2026: profit ₹120 Cr, up 20% on a year ago", "good")
    assert results_text(now, None)[0] == "Results for the quarter to 30 Sep 2026: profit ₹120 Cr"
    loss = QuarterlyResult(ticker="X.NS", quarter_end=date(2026, 9, 30), consolidated=True, profit=-5.4e10)
    assert results_text(loss, before) == ("Results for the quarter to 30 Sep 2026: loss ₹5,400 Cr, against a profit a year ago", "bad")
    assert results_text(now, loss)[0].endswith("profit ₹120 Cr, against a loss a year ago")
    assert results_text(loss, loss)[0].endswith("after a loss a year ago too")


def test_upcoming_events_only_held_and_within_two_weeks():
    today = date(2026, 11, 20)
    events = {
        "earnings": [{"ticker": "ITC.NS", "date": "2026-11-25"}, {"ticker": "ITC.NS", "date": "2026-12-20"},
                     {"ticker": "TCS.NS", "date": "2026-11-21"}],
        "corporate_actions": [{"ticker": "ITC.NS", "ex_date": "2026-11-22", "subject": "Interim Dividend - Rs 6.50"},
                              {"ticker": "ITC.NS", "ex_date": None, "subject": "Bonus"}],
    }
    got = upcoming_events(events, {"ITC.NS"}, today)
    assert [(u.day, u.text) for u in got["ITC.NS"]] == [
        (date(2026, 11, 25), "Board meeting on results"),
        (date(2026, 11, 22), "Ex-date: Interim Dividend - Rs 6.50"),
    ]
    assert all(u.upcoming for u in got["ITC.NS"]) and "TCS.NS" not in got


@pytest.mark.asyncio
async def test_updates_feed_per_portfolio(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {})
    today = utcnow().date()

    async def feeds(day):
        return {"earnings": [{"ticker": "ITC.NS", "date": (today + timedelta(days=3)).isoformat()}], "corporate_actions": []}

    monkeypatch.setattr(nse_market, "event_feeds", feeds)
    now = utcnow()
    user_id = (await db_session.execute(select(User.id).where(User.email == "test@quantara.com"))).scalar_one()
    db_session.add_all([
        Stock(ticker="ITC.NS", name="ITC", sector="FMCG", price=410.0, previous_close=400.0, price_updated_at=now,
              filing_updated_at=now - timedelta(days=1)),
        Stock(ticker="TCS.NS", name="TCS", sector="IT", price=4000.0, previous_close=4000.0, price_updated_at=now),
    ])
    await db_session.flush()
    db_session.add_all([
        Signal(ticker="ITC.NS", signal_type="promoter_holding_change", strength=60, confidence=0.7,
               data={"direction": "bullish", "change_pp": 1.5}, timestamp=now - timedelta(days=2)),
        Signal(ticker="ITC.NS", signal_type="large_deal", strength=60, confidence=0.7,
               data={"direction": "bullish", "net_pct_of_company": 0.5}, timestamp=now - timedelta(days=30)),  # too old
        PriceAlert(user_id=user_id, ticker="ITC.NS", direction="above", target_price=405, triggered_at=now),
        QuarterlyResult(ticker="ITC.NS", quarter_end=date(2026, 9, 30), consolidated=True, profit=5.5e10, filed_at=now),
        QuarterlyResult(ticker="ITC.NS", quarter_end=date(2025, 9, 30), consolidated=True, profit=5.0e10,
                        filed_at=datetime(2025, 10, 30)),
        VerdictSnapshot(day=today - timedelta(days=1), ticker="ITC.NS", risk_level="Moderate", verdict="Hold", final_score=55, price=400),
        VerdictSnapshot(day=today, ticker="ITC.NS", risk_level="Moderate", verdict="Buy", final_score=70, price=410),
        VerdictSnapshot(day=today, ticker="ITC.NS", risk_level="Aggressive", verdict="Avoid", final_score=30, price=410),
    ])
    await db_session.commit()
    headers = await _headers(client)
    created = await client.post("/api/v1/portfolio/", headers=headers, json={"name": "Core", "positions": [
        {"ticker": "ITC.NS", "weight": 0, "shares": 10, "cost_basis": 300},
        {"ticker": "TCS.NS", "weight": 0, "shares": 1, "cost_basis": 3000},
    ]})
    assert created.status_code == 201

    resp = await client.get("/api/v1/portfolio/updates", headers=headers)
    assert resp.status_code == 200
    [core] = resp.json()["portfolios"]
    assert core["name"] == "Core"
    assert core["performance"]["totals"][0]["market_value"] == 4100.0 + 4000.0
    assert set(core["updates"]) == {"ITC.NS"}  # nothing happened to TCS
    texts = [u["text"] for u in core["updates"]["ITC.NS"]]
    assert "Promoter stake up 1.50 points this quarter" in texts
    assert "Price alert hit: went above 405" in texts
    assert "Earnings-call transcript in; AI summary ready" in texts
    assert "Results for the quarter to 30 Sep 2026: profit ₹5,500 Cr, up 10% on a year ago" in texts
    assert "Verdict changed: Hold → Buy" in texts  # the Moderate call only
    assert not any("Avoid" in t or "net buying" in t for t in texts)
    assert texts[-1] == "Board meeting on results" and core["updates"]["ITC.NS"][-1]["upcoming"] is True
