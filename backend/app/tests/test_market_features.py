"""Market overview, events, themes, technicals, saved screens and shared chats."""

from datetime import date, timedelta

import pytest

from app.api.v1 import market
from app.core.clock import utcnow
from app.models.stock import Stock
from app.services import nse_market
from app.services.event_alerts import digest
from app.services.nse_market import (
    action_kind,
    parse_earnings,
    parse_flows,
    parse_indices,
    parse_ipos,
)
from app.services.technicals import indicators


def test_indices_split_headline_sectors_and_breadth():
    rows = [
        {"key": "SECTORAL INDICES", "index": "NIFTY IT", "last": "100", "variation": -2, "percentChange": -2.0},
        {"key": "SECTORAL INDICES", "index": "NIFTY AUTO", "last": "1,200.5", "variation": 12, "percentChange": 1.0},
        {"key": "BROAD", "index": "NIFTY 50", "last": 25000, "variation": 50, "percentChange": 0.2},
        {"key": "BROAD", "index": "NIFTY 500", "last": 1, "advances": "231", "declines": "266", "unchanged": "4"},
    ]
    parsed = parse_indices(rows)
    assert [i["name"] for i in parsed["headline"]] == ["NIFTY 50"]
    assert [s["name"] for s in parsed["sectors"]] == ["NIFTY AUTO", "NIFTY IT"]
    assert parsed["sectors"][0]["last"] == 1200.5
    assert parsed["breadth"] == {"advances": 231, "declines": 266, "unchanged": 4}


def test_flows_and_earnings_parse_nse_formats():
    flows = parse_flows([{"category": "DII", "date": "09-Nov-2026", "buyValue": "12,764.97", "sellValue": "19937.5", "netValue": "-7172.53"}])
    assert flows == [{"category": "DII", "date": "2026-11-09", "buy": 12764.97, "sell": 19937.5, "net": -7172.53}]
    rows = [
        {"symbol": "LATE", "company": "L", "purpose": "Financial Results", "bm_desc": "x", "date": "20-Nov-2026"},
        {"symbol": "SOON", "company": "S", "purpose": "Financial Results/Dividend", "bm_desc": "y", "date": "11-Nov-2026"},
        {"symbol": "PAST", "company": "P", "purpose": "Financial Results", "bm_desc": "z", "date": "01-Nov-2026"},
        {"symbol": "FUND", "company": "F", "purpose": "Fund Raising", "bm_desc": "w", "date": "12-Nov-2026"},
    ]
    assert [e["ticker"] for e in parse_earnings(rows, date(2026, 11, 10))] == ["SOON.NS", "LATE.NS"]


@pytest.mark.parametrize("subject,kind", [
    ("Interim Dividend - Rs 2.50 Per Share", "Dividend"),
    ("Bonus 1:1", "Bonus"),
    ("Face Value Split (Sub-Division) - From Rs 10 To Rs 2", "Split"),
    ("Rights 1:5 @ Premium Rs 10", "Rights"),
    ("Buy Back", "Buyback"),
    ("Annual General Meeting", "Other"),
])
def test_corporate_action_kinds(subject, kind):
    assert action_kind(subject) == kind


def test_ipos_read_both_feed_shapes_in_status_order():
    open_issue = {"symbol": "NEW", "companyName": "New Ltd", "issueStartDate": "10-NOV-2026", "issueEndDate": "12-NOV-2026", "noOfTime": "3.5"}
    past = {"symbol": "OLD", "company": "Old Ltd", "ipoStartDate": "02-NOV-2026", "ipoEndDate": "04-NOV-2026", "listingDate": "09-NOV-2026", "priceRange": "Rs.88 to Rs.94", "securityType": "SME"}
    ipos = parse_ipos([open_issue], None, [past])
    assert [(i["symbol"], i["status"]) for i in ipos] == [("NEW", "Open"), ("OLD", "Listed")]
    assert ipos[0]["start_date"] == "2026-11-10" and ipos[0]["subscribed_times"] == 3.5
    assert ipos[1]["start_date"] == "2026-11-02" and ipos[1]["segment"] == "SME"


def test_indicators_on_known_series():
    rising = [100.0 + i for i in range(250)]
    result = indicators(rising)
    assert result["rsi_14"] == 100.0  # no falls at all
    assert result["sma_20"] == pytest.approx(339.5)
    assert result["sma_200"] == pytest.approx(249.5)
    assert result["high_1y"] == 349.0 and result["pct_from_high"] == 0
    assert any("above its 200-day" in n for n in result["notes"])
    # 14 equal rises and falls alternating sit near the middle
    choppy = [100.0 + (i % 2) for i in range(60)]
    assert 40 < indicators(choppy)["rsi_14"] < 60
    assert indicators(choppy)["sma_200"] is None
    assert indicators([1.0] * 29) is None


async def _headers(client):
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_overview_movers_skip_stale_prices_and_report_a_missing_feed(client, db_session, monkeypatch):
    now = utcnow()
    db_session.add_all([
        Stock(ticker="UP.NS", name="Up", sector="IT", price=110, previous_close=100, price_updated_at=now, pe_ratio=20, turnover_1d=5e7),
        Stock(ticker="DOWN.NS", name="Down", sector="IT", price=90, previous_close=100, price_updated_at=now, turnover_1d=2e7),
        # A penny stock up 40% on ₹10 lakh of trades isn't a top gainer
        Stock(ticker="PENNY.NS", name="Penny", price=3.5, previous_close=2.5, price_updated_at=now, turnover_1d=1e6),
        Stock(ticker="STALE.NS", name="Stale", sector="IT", price=500, previous_close=100, price_updated_at=now - timedelta(days=30)),
    ])
    await db_session.commit()

    async def feeds():
        return None, None

    async def quotes():
        return dict(market._FALLBACK_QUOTES)

    monkeypatch.setattr(nse_market, "market_feeds", feeds)
    monkeypatch.setattr(market, "_get_quotes", quotes)
    resp = await client.get("/api/v1/market/overview", headers=await _headers(client))
    assert resp.status_code == 200
    data = resp.json()
    assert data["indices"] is None and data["flows"] is None  # unavailable, not invented
    assert [g["ticker"] for g in data["gainers"]] == ["UP.NS"]
    assert [g["ticker"] for g in data["losers"]] == ["DOWN.NS"]
    assert data["sectors"] == [{"sector": "IT", "stocks": 2, "avg_change_pct": 0.0, "avg_pe": 20.0}]


@pytest.mark.asyncio
async def test_saved_screens_replace_by_name_and_stay_private(client):
    headers = await _headers(client)
    first = await client.post("/api/v1/screens/", headers=headers, json={"name": "Value", "filters": {"roe_min": "15"}})
    assert first.status_code == 200
    again = await client.post("/api/v1/screens/", headers=headers, json={"name": "Value", "filters": {"roe_min": "20"}, "sort": "-roe"})
    assert again.json()["id"] == first.json()["id"]
    listed = (await client.get("/api/v1/screens/", headers=headers)).json()
    assert [(s["name"], s["filters"], s["sort"]) for s in listed] == [("Value", {"roe_min": "20"}, "-roe")]
    assert (await client.get("/api/v1/screens/")).status_code in (401, 403)

    await client.post("/api/v1/auth/register", json={"email": "other@quantara.com", "password": "Sup3r-secret-pw!", "full_name": "O"})
    login = await client.post("/api/v1/auth/login", json={"email": "other@quantara.com", "password": "Sup3r-secret-pw!"})
    if login.status_code == 200:
        other = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await client.delete(f"/api/v1/screens/{first.json()['id']}", headers=other)).status_code == 404
    assert (await client.delete(f"/api/v1/screens/{first.json()['id']}", headers=headers)).status_code == 204


async def _other_user(client):
    """A second signed-in user, to check what someone else can and can't read."""
    creds = {"email": "reader@quantara.com", "password": "Sup3r-secret-pw!"}
    await client.post("/api/v1/auth/register", json={**creds, "full_name": "R"})
    login = await client.post("/api/v1/auth/login", json=creds)
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_chats_are_saved_private_and_shared_only_with_signed_in_users(client):
    headers, other = await _headers(client), await _other_user(client)
    messages = [{"role": "user", "content": "Is TCS risky?", "tickers": []},
                {"role": "assistant", "content": "Moderately.", "tickers": ["TCS.NS"]}]
    saved = await client.post("/api/v1/chat/saved", headers=headers, json={"messages": messages[:1]})
    token = saved.json()["token"]
    assert len(token) >= 40
    updated = await client.put(f"/api/v1/chat/saved/{token}", headers=headers, json={"messages": messages})
    assert updated.json()["token"] == token
    assert (await client.put(f"/api/v1/chat/saved/{token}", headers=other, json={"messages": messages})).status_code == 404

    # Saved: the owner reads it; nobody else, and never without signing in
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=headers)).json()["messages"] == messages
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/chat/shared/{token}")).status_code in (401, 403)

    # Shared: the same chat (no copy) opens for other signed-in users, still not for the signed-out
    shared = await client.post("/api/v1/chat/share", headers=headers, json={"messages": messages, "listed": True, "token": token})
    assert shared.json()["token"] == token and shared.json()["listed"] is True
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=other)).status_code == 200
    assert (await client.get(f"/api/v1/chat/shared/{token}")).status_code in (401, 403)

    # Stop sharing: private again, but kept for the owner
    await client.post("/api/v1/chat/share", headers=headers, json={"messages": messages, "listed": False, "token": token})
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=headers)).status_code == 200

    assert (await client.delete(f"/api/v1/chat/shared/{token}", headers=other)).status_code == 404
    assert (await client.delete(f"/api/v1/chat/shared/{token}", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/chat/shared/{token}", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/market/status")).status_code in (401, 403)  # nothing is public


def test_event_digest_covers_only_held_stocks_on_that_day():
    events = {
        "earnings": [
            {"ticker": "TCS.NS", "date": "2026-11-11"},
            {"ticker": "OTHER.NS", "date": "2026-11-11"},
            {"ticker": "TCS.NS", "date": "2026-11-12"},
        ],
        "corporate_actions": [{"ticker": "ITC.NS", "ex_date": "2026-11-11", "subject": "Dividend - Rs 5"}],
    }
    text = digest(events, {"TCS.NS", "ITC.NS"}, date(2026, 11, 11))
    assert "TCS.NS: results" in text and "ITC.NS: ex-date for Dividend - Rs 5" in text and "OTHER" not in text
    assert digest(events, {"TCS.NS"}, date(2026, 11, 20)) is None
    assert digest({"earnings": None, "corporate_actions": None}, {"TCS.NS"}, date(2026, 11, 11)) is None


@pytest.mark.asyncio
async def test_daily_digest_has_market_highlights_and_only_watched_stocks(db_session):
    from sqlalchemy import select

    from app.models.price_alert import PriceAlert
    from app.models.signal import Signal
    from app.models.user import User
    from app.models.watchlist import WatchlistItem
    from app.services.event_alerts import build_daily_digest

    now = utcnow()
    db_session.add_all([
        Stock(ticker="ITC.NS", name="ITC", price=412.0, previous_close=400.0, price_updated_at=now,
              turnover_1d=5e9, filing_updated_at=now),
        Stock(ticker="TCS.NS", name="TCS", price=3000.0, previous_close=3100.0, price_updated_at=now, turnover_1d=5e9),
        Stock(ticker="OTHER.NS", name="Other Co", price=10.0, previous_close=9.0, price_updated_at=now,
              turnover_1d=5e9, filing_updated_at=now),
    ])
    await db_session.flush()
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    db_session.add_all([
        WatchlistItem(user_id=user.id, ticker="ITC.NS"),
        PriceAlert(user_id=user.id, ticker="ITC.NS", direction="above", target_price=410, triggered_at=now),
        Signal(ticker="ITC.NS", signal_type="large_deal", strength=70, confidence=80, timestamp=now),
        # Saved today but about a months-old event (a backfill): not news
        Signal(ticker="ITC.NS", signal_type="promoter_pledge", strength=70, confidence=80,
               timestamp=now - timedelta(days=60)),
    ])
    await db_session.commit()
    events = {"earnings": [{"ticker": "ITC.NS", "date": "2026-11-14"}], "corporate_actions": []}

    text = await build_daily_digest(db_session, {"NIFTY 50": (25100.0, 100.0)}, events, date(2026, 11, 13))
    assert "Market close, Fri 13 Nov" in text and "NIFTY 50 25,100 (+0.40%)" in text
    assert "Top gainers: Other Co +11.1%, ITC +3.0%" in text and "Top losers: TCS -3.2%" in text
    [mine] = [line for line in text.splitlines() if line.startswith("• <")]
    assert "/research/ITC.NS|ITC>" in mine and "₹412.00 (+3.0%)" in mine
    assert "price alert hit (above 410)" in mine and "large deal" in mine and "transcript in" in mine
    assert "pledge" not in mine
    assert "Tomorrow (Sat 14 Nov)" in text and "ITC.NS: results board meeting" in text
    assert "Other Co (" not in text and "OTHER.NS" not in text  # not watched: only in the market movers

@pytest.mark.asyncio
async def test_gallery_has_all_my_chats_and_only_others_shared_ones(client):
    headers, other = await _headers(client), await _other_user(client)
    chat = [{"role": "user", "content": "Is TCS a buy?"}, {"role": "assistant", "content": "Hold.", "tickers": ["TCS.NS"]}]
    private = (await client.post("/api/v1/chat/saved", headers=headers, json={"messages": chat})).json()["token"]
    listed = (await client.post("/api/v1/chat/share", headers=headers, json={"messages": chat, "listed": True})).json()["token"]

    mine = (await client.get("/api/v1/chat/gallery", headers=headers)).json()
    assert {(c["token"], c["mine"], c["listed"]) for c in mine} == {(private, True, False), (listed, True, True)}
    assert mine[0]["question"] == "Is TCS a buy?" and mine[0]["tickers"] == ["TCS.NS"] and mine[0]["messages"] == 2

    theirs = (await client.get("/api/v1/chat/gallery", headers=other)).json()
    assert [(c["token"], c["mine"]) for c in theirs] == [(listed, False)]  # never someone's private chat
    assert (await client.get("/api/v1/chat/gallery")).status_code in (401, 403)  # signed-in users only


@pytest.mark.asyncio
async def test_daily_digest_goes_out_once_on_weekdays_after_the_close(monkeypatch):
    from datetime import datetime

    from redis.asyncio import Redis

    from app.core.config import settings
    from app.services import event_alerts

    sent: list[str] = []
    slack_up = [False]

    async def fake_slack(text: str) -> bool:
        sent.append(text)
        return slack_up[0]

    async def no_indices() -> dict:
        return {}

    async def no_events(today: date) -> dict:
        return {}

    async def built(db, indices, events, today) -> str:
        return f"digest {today}"

    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.example.com/x")
    monkeypatch.setattr(settings, "slack_bot_token", None)  # webhook only: one shared digest
    monkeypatch.setattr(event_alerts, "notify_slack", fake_slack)
    monkeypatch.setattr(event_alerts, "_market_indices", no_indices)
    monkeypatch.setattr(event_alerts, "event_feeds", no_events)
    monkeypatch.setattr(event_alerts, "build_daily_digest", built)
    redis = Redis.from_url(settings.redis_url)
    await redis.delete("digest:sent:2030-01-07")  # a Monday no real digest uses
    try:
        assert not await event_alerts.send_daily_digest_if_due(datetime(2030, 1, 5, 17, tzinfo=event_alerts.IST))  # Saturday
        assert not await event_alerts.send_daily_digest_if_due(datetime(2030, 1, 7, 15, tzinfo=event_alerts.IST))  # market open
        # Slack refused it: not counted as sent, so the next check tries again
        assert not await event_alerts.send_daily_digest_if_due(datetime(2030, 1, 7, 16, 5, tzinfo=event_alerts.IST))
        slack_up[0] = True
        assert await event_alerts.send_daily_digest_if_due(datetime(2030, 1, 7, 16, 15, tzinfo=event_alerts.IST))
        assert not await event_alerts.send_daily_digest_if_due(datetime(2030, 1, 7, 16, 25, tzinfo=event_alerts.IST))
        assert sent == ["digest 2030-01-07"] * 2
    finally:
        await redis.delete("digest:sent:2030-01-07")
        await redis.aclose()


@pytest.mark.asyncio
async def test_with_the_bot_each_linked_user_gets_their_own_digest_and_only_failures_retry(monkeypatch):
    from datetime import datetime

    from redis.asyncio import Redis

    from app.core.config import settings
    from app.services import event_alerts

    sent: list[tuple[int, str]] = []
    down = {9}

    async def fake_slack(text: str, user_id: int | None = None) -> bool:
        sent.append((user_id, text))
        return user_id not in down

    async def nothing(*a) -> dict:
        return {}

    async def built(db, indices, events, today) -> str:
        return "market"

    async def section(db, user_id, today) -> str | None:
        return f"portfolio of {user_id}" if user_id == 8 else None

    monkeypatch.setattr(settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(settings, "slack_users", "UA:8,UB:9,UC:8")
    monkeypatch.setattr(event_alerts, "notify_slack", fake_slack)
    monkeypatch.setattr(event_alerts, "_market_indices", nothing)
    monkeypatch.setattr(event_alerts, "event_feeds", nothing)
    monkeypatch.setattr(event_alerts, "build_daily_digest", built)
    monkeypatch.setattr(event_alerts, "portfolio_section", section)
    keys = ["digest:sent:2030-01-08:8", "digest:sent:2030-01-08:9"]
    redis = Redis.from_url(settings.redis_url)
    await redis.delete(*keys)
    at = datetime(2030, 1, 8, 16, 5, tzinfo=event_alerts.IST)
    try:
        assert await event_alerts.send_daily_digest_if_due(at)
        assert sent == [(8, "market\n\nportfolio of 8"), (9, "market")]
        down.clear()
        assert await event_alerts.send_daily_digest_if_due(at)  # only 9, whose send failed, again
        assert sent[2:] == [(9, "market")]
        assert not await event_alerts.send_daily_digest_if_due(at)
    finally:
        await redis.delete(*keys)
        await redis.aclose()


@pytest.mark.asyncio
async def test_portfolio_section_shows_the_mix_and_verdicts_that_changed(db_session, monkeypatch):
    from sqlalchemy import select

    from app.models.portfolio import Portfolio, PortfolioPosition
    from app.models.user import User
    from app.models.verdict_snapshot import VerdictSnapshot
    from app.services import price_service
    from app.services.event_alerts import portfolio_section

    monkeypatch.setattr(price_service, "fetch_quotes", lambda tickers: {})
    user = (await db_session.execute(select(User))).scalars().first()
    user.risk_level = "Moderate"
    db_session.add_all([
        Stock(ticker="AAA.NS", name="Example A", sector="Banks", price=100.0, price_updated_at=utcnow()),
        Stock(ticker="BBB.NS", name="Example B", sector="Energy", price=100.0, price_updated_at=utcnow()),
    ])
    await db_session.flush()
    pf = Portfolio(user_id=user.id, name="Main")
    pf.positions = [PortfolioPosition(ticker="AAA.NS", shares=10, cost_basis=90, weight=0.5),
                    PortfolioPosition(ticker="BBB.NS", shares=10, cost_basis=90, weight=0.5)]
    db_session.add(pf)
    day1, day2 = date(2030, 1, 7), date(2030, 1, 8)
    for day, a, b in ((day1, "Hold", "Buy"), (day2, "Avoid", "Buy")):
        db_session.add_all([
            VerdictSnapshot(day=day, ticker="AAA.NS", risk_level="Moderate", verdict=a, final_score=50, price=100),
            VerdictSnapshot(day=day, ticker="BBB.NS", risk_level="Moderate", verdict=b, final_score=50, price=100),
            VerdictSnapshot(day=day, ticker="AAA.NS", risk_level="Aggressive", verdict="Buy", final_score=50, price=100),
        ])
    await db_session.commit()

    text = await portfolio_section(db_session, user.id, day2)
    assert "Mix: 100% equity (target 70/20/5/5 equity/debt/cash/gold): off target" in text
    assert "Verdicts changed since Mon 07 Jan: Example A Hold → Avoid" in text
    assert "Example B" not in text.split("Verdicts changed")[1]  # Buy both days
    assert await portfolio_section(db_session, 999999, day2) is None
