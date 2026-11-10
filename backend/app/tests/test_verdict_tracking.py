"""Daily verdict snapshots and the track record built from them."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models.stock import Stock
from app.models.verdict_snapshot import VerdictSnapshot
from app.services.verdict_tracking import snapshot_verdicts, track_record

DAY0 = date(2026, 1, 5)


@pytest.mark.asyncio
async def test_snapshot_records_each_rated_stock_once_a_day(db_session):
    db_session.add_all([
        Stock(ticker="GOOD", sector="Technology", price=100.0, research_score=80.0, risk_score=50.0),
        Stock(ticker="NOREPORT", price=10.0, risk_score=50.0),  # unrated: no research yet
    ])
    await db_session.commit()

    assert await snapshot_verdicts(db_session, DAY0) == 3  # one per risk profile
    await snapshot_verdicts(db_session, DAY0)  # the job runs every 15 minutes; the day is already recorded
    count = (await db_session.execute(select(func.count()).select_from(VerdictSnapshot))).scalar_one()
    assert count == 3
    moderate = (await db_session.execute(
        select(VerdictSnapshot).where(VerdictSnapshot.risk_level == "Moderate")
    )).scalar_one()
    assert moderate.verdict == "Buy" and moderate.price == 100.0


@pytest.mark.asyncio
async def test_track_record_compares_each_verdict_with_all_rated_stocks(db_session):
    def snap(day, ticker, verdict, price):
        return VerdictSnapshot(day=day, ticker=ticker, risk_level="Moderate", verdict=verdict, final_score=60, price=price)

    later = DAY0 + timedelta(days=32)  # the job missed day 30; a price within a week still counts
    db_session.add_all([
        snap(DAY0, "UP", "Buy", 100.0), snap(later, "UP", "Buy", 120.0),  # +20%
        snap(DAY0, "FLAT", "Hold", 50.0), snap(later, "FLAT", "Hold", 50.0),  # 0%
        snap(DAY0, "DOWN", "Avoid", 10.0), snap(later, "DOWN", "Avoid", 8.0),  # -20%
        snap(DAY0, "GONE", "Buy", 10.0),  # no later price: left out
    ])
    await db_session.commit()

    early = await track_record(db_session, "Moderate", 30, today=DAY0 + timedelta(days=10))
    assert early["verdicts"] == [] and early["first_results_on"] == DAY0 + timedelta(days=30)

    record = await track_record(db_session, "Moderate", 30, today=later)
    assert record["all_rated_avg_return_pct"] == 0.0
    by_verdict = {v["verdict"]: v for v in record["verdicts"]}
    assert by_verdict["Buy"] == {"verdict": "Buy", "count": 1, "avg_return_pct": 20.0,
                                 "vs_all_rated_pct": 20.0, "share_that_rose_pct": 100.0}
    assert by_verdict["Avoid"]["vs_all_rated_pct"] == -20.0
    assert (await track_record(db_session, "Aggressive", 30, today=later))["verdicts"] == []


@pytest.mark.asyncio
async def test_track_record_endpoint_only_takes_known_horizons(client):
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    ok = await client.get("/api/v1/recommendations/track-record?horizon_days=90", headers=headers)
    assert ok.status_code == 200 and ok.json()["verdicts"] == [] and ok.json()["risk_level"] == "Moderate"
    assert (await client.get("/api/v1/recommendations/track-record?horizon_days=7", headers=headers)).status_code == 422
