"""Nightly research picks watched/held stocks whose report is missing, stale or has no outlook."""

from datetime import timedelta

import pytest

from app.core.clock import utcnow
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.research import ResearchReport
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.services import held_research


def _report(ticker, *, age_hours=1, outlook=True):
    body = {"summary": "x", **({"outlook_score": 60.0} if outlook else {})}
    return ResearchReport(ticker=ticker, structured_json=body, confidence_score=80.0,
                          updated_at=utcnow() - timedelta(hours=age_hours))


@pytest.mark.asyncio
async def test_only_stale_watched_or_held_reports_are_refreshed(db_session, monkeypatch):
    user = (await db_session.execute(User.__table__.select())).first()
    db_session.add_all([Stock(ticker=t) for t in ["FRESH", "OLD", "NOOUTLOOK", "NONE", "HELD", "UNWATCHED"]])
    await db_session.flush()
    portfolio = Portfolio(user_id=user.id, name="Core")
    db_session.add(portfolio)
    await db_session.flush()
    db_session.add_all([
        *(WatchlistItem(user_id=user.id, ticker=t) for t in ["FRESH", "OLD", "NOOUTLOOK", "NONE"]),
        PortfolioPosition(portfolio_id=portfolio.id, ticker="HELD", weight=1.0),
        _report("FRESH"), _report("OLD", age_hours=48), _report("NOOUTLOOK", outlook=False),
        _report("HELD", age_hours=30), _report("UNWATCHED", age_hours=48),
    ])
    await db_session.commit()

    stale = await held_research.stale_held_tickers(db_session)
    assert stale[0] == "NONE" and set(stale) == {"NONE", "OLD", "NOOUTLOOK", "HELD"}
    assert await held_research.stale_held_tickers(db_session, limit=2) == ["NONE", "OLD"]  # oldest first

    generated = []

    class FakeEngine:
        async def generate_research_report(self, db, ticker, **kwargs):
            generated.append(ticker)
            if ticker == "OLD":
                raise RuntimeError("LLM down")  # one failure doesn't stop the run
            return {"ticker": ticker}

    monkeypatch.setattr("app.services.research_engine.ResearchEngine", FakeEngine)
    assert await held_research.refresh_held_research(db_session) == 3
    assert set(generated) == {"NONE", "OLD", "NOOUTLOOK", "HELD"}
