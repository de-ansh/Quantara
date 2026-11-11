"""IPO analysis from NSE issue data and the prospectus."""

import pytest

from app.services import ipo_analysis, nse_market
from app.services.ipo_analysis import issue_pros_cons, parse_issue, rhp_sections


def _detail(size: str, cats: list[tuple[str, str]], segment: str = "EQUITY") -> dict:
    return {
        "companyName": "Steel Co Limited",
        "metaInfo": {"symbol": "STEEL", "industry": "Iron & Steel Products", "segment": segment},
        "issueInfo": {"dataList": [
            {"title": "Issue Size", "value": f'"{size}"'},
            {"title": "Price Range", "value": "Rs. 78/- to Rs. 82/- per Equity Share"},
            {"title": "Bid Lot", "value": "182 Equity Shares and in multiples thereof"},
            {"title": "Red Herring Prospectus", "value": "https://nsearchives.nseindia.com/content/ipo/RHP_STEEL.zip"},
        ]},
        "activeCat": {"dataList": [{"category": "Category", "noOfTotalMeant": "No. of times"}]
                      + [{"category": c, "noOfTotalMeant": t} for c, t in cats]},
    }


CATS = [("Qualified Institutional Buyers(QIBs)", "35.49"), ("Foreign Institutional Investors(FIIs)", ""),
        ("Non Institutional Investors", "158.31"), ("Non Institutional Investors(Bid amount of more than Ten Lakh Rupees)", "183.5"),
        ("Retail Individual Investors(RIIs)", "33.73"), ("Total", "60.77")]


def test_fresh_issue_in_rupees_and_strong_demand():
    issue = parse_issue(_detail("Initial Public Offer comprising of Fresh Issue aggregating upto Rs. 1,830.57 million (including Anchor portion)", CATS))
    assert issue["fresh_issue_crore"] == 183.06 and issue["offer_for_sale_share"] == 0
    assert issue["subscription"] == {"qib": 35.49, "nii": 158.31, "retail": 33.73, "total": 60.77}
    pros, cons = issue_pros_cons(issue)
    assert "Institutions bid 35.5x their quota" in pros and any("no existing holder is selling" in p for p in pros) and cons == []


def test_offer_for_sale_in_shares_crore_mix_and_sme_zeros():
    shares = parse_issue(_detail("Fresh Issue of up to 10,00,000 Equity Shares and Offer for sale of up to 30,00,000 Equity Shares", [("Total", "0.00")], "SME"))
    assert shares["offer_for_sale_share"] == 0.75 and shares["subscription"] == {}  # zeros mean no data
    pros, cons = issue_pros_cons(shares)
    assert any("75% of the issue is existing shareholders selling" in c for c in cons)
    assert any("SME platform" in c for c in cons)
    money = parse_issue(_detail("Fresh Issue aggregating up to ₹ 500 crore and an Offer for Sale aggregating up to ₹ 1,500 crore", []))
    assert money["fresh_issue_crore"] == 500 and money["offer_for_sale_crore"] == 1500 and money["offer_for_sale_share"] == 0.75


def test_prospectus_sections_skip_the_contents_page():
    pages = ["cover"] * 3 + ["TABLE OF CONTENTS BASIS FOR ISSUE PRICE 133"] + ["filler"] * 6
    pages += ["BASIS FOR ISSUE PRICE\nEPS 4.2 P/E at upper band 19.5x vs peers 28x"] + ["filler"] * 3
    text = rhp_sections(pages)
    assert "## Basis for the price" in text and "P/E at upper band 19.5x" in text and "TABLE OF CONTENTS" not in text


@pytest.mark.asyncio
async def test_endpoint_merges_rules_with_the_ai_and_caches(client, monkeypatch):
    calls = {"llm": 0}

    async def detail(path: str, ttl: float = 0) -> dict:
        assert path == "api/ipo-detail?symbol=STEEL&series=EQ"
        return _detail("Fresh Issue aggregating upto Rs. 1,830.57 million", CATS)

    async def sections(url):
        return "## Basis for the price\nP/E 19.5x vs peers 28x"

    async def llm(issue, text):
        calls["llm"] += 1
        assert "P/E 19.5x" in text and issue["fresh_issue_crore"] == 183.06
        return {"summary": "Steel maker.", "pros": ["Priced below peers (19.5x vs 28x)"], "cons": ["Cyclical demand"],
                "recommendation": "Apply", "reasoning": "Cheap and in demand.", "confidence": 70}

    monkeypatch.setattr(nse_market, "nse_json", detail)
    monkeypatch.setattr(ipo_analysis, "fetch_rhp_sections", sections)
    monkeypatch.setattr(ipo_analysis, "llm_analysis", llm)
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    from redis.asyncio import Redis

    from app.core.config import settings

    redis = Redis.from_url(settings.redis_url)
    await redis.delete("ipo-analysis:STEEL:EQ")
    try:
        first = await client.get("/api/v1/market/ipos/steel/analysis", headers=headers)
        await _check(client, headers, first, calls)
    finally:
        await redis.delete("ipo-analysis:STEEL:EQ")
        await redis.aclose()


async def _check(client, headers, first, calls):
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["recommendation"] == "Apply" and body["read_prospectus"] is True
    assert body["pros"][0] == "Institutions bid 35.5x their quota" and "Priced below peers (19.5x vs 28x)" in body["pros"]
    again = await client.get("/api/v1/market/ipos/STEEL/analysis", headers=headers)
    assert again.json()["cached"] is True and calls["llm"] == 1
    assert (await client.get("/api/v1/market/ipos/BAD$/analysis", headers=headers)).status_code in (404, 422)
