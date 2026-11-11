"""Data-based Buy / Hold / Avoid for every stock."""

import pytest

from app.models.stock import Stock
from app.services.stock_call import data_call


def _stock(**kw) -> Stock:
    return Stock(ticker="X.NS", name="X", **kw)


def test_strong_numbers_make_a_buy_with_reasons():
    call = data_call(_stock(roe_pct=24, roce_pct=26, revenue_cagr_3y_pct=18, profit_cagr_3y_pct=22,
                            debt_to_equity=0.1, pe_ratio=18, risk_score=30))
    assert call.verdict == "Buy" and call.score >= 65
    assert call.pros[0] == "High return on equity (24%)" and call.cons == []


def test_weak_numbers_make_an_avoid():
    call = data_call(_stock(roe_pct=4, revenue_cagr_3y_pct=-5, profit_cagr_3y_pct=-12, debt_to_equity=2.4,
                            pe_ratio=-3, return_1y_pct=-40))
    assert call.verdict == "Avoid"
    assert "Loss-making (no positive earnings)" in call.cons and "Heavy debt (debt/equity 2.40)" in call.cons


def test_too_little_data_is_unrated_and_mixed_is_hold():
    assert data_call(_stock(roe_pct=30, pe_ratio=15)).verdict == "Unrated"
    assert data_call(_stock(roe_pct=16, revenue_cagr_3y_pct=5, pe_ratio=30, debt_to_equity=0.8)).verdict == "Hold"


def test_risk_profile_caps_a_buy_and_banks_skip_debt():
    strong = {"roe_pct": 24, "roce_pct": 26, "revenue_cagr_3y_pct": 18, "profit_cagr_3y_pct": 22, "pe_ratio": 18, "risk_score": 60}
    assert data_call(_stock(**strong), "Moderate").verdict == "Buy"
    capped = data_call(_stock(**strong), "Conservative")
    assert capped.verdict == "Hold" and any("Riskier than a conservative profile" in c for c in capped.cons)
    bank = data_call(_stock(sector="Financial Services", debt_to_equity=8.0, **strong))
    assert not any("debt" in c.lower() for c in bank.cons)


@pytest.mark.asyncio
async def test_verdict_falls_back_to_the_data_call_and_search_shows_it(client, db_session):
    db_session.add(Stock(ticker="GOOD.NS", name="Good Co", price=100.0, roe_pct=24, roce_pct=26,
                         revenue_cagr_3y_pct=18, profit_cagr_3y_pct=22, debt_to_equity=0.1, pe_ratio=18))
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    v = (await client.get("/api/v1/recommendations/GOOD.NS/verdict", headers=headers)).json()
    assert v["verdict"] == "Buy" and v["basis"] == "data" and v["pros"] and v["missing"]
    unknown = (await client.get("/api/v1/recommendations/NOPE.NS/verdict", headers=headers)).json()
    assert unknown["verdict"] == "Unrated"
