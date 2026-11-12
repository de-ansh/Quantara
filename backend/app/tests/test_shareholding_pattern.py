"""Institutional split of the shareholding pattern from NSE XBRL, in both filing formats."""

from datetime import date

import pytest

from app.models.shareholding import Shareholding
from app.services import nse_market, shareholding
from app.services.shareholding import parse_pattern_xbrl


def _xbrl(values: dict[str, float], suffix: str, holders: int = 2_579_099) -> str:
    facts = "".join(
        f'<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="{ctx}{suffix}" decimals="INF" unitRef="pure">{v}</in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares>'
        for ctx, v in values.items()
    )
    return f'<xbrli:xbrl>{facts}<in-bse-shp:NumberOfShareholders contextRef="ShareholdingPattern{suffix}" decimals="INF" unitRef="shares">{holders}</in-bse-shp:NumberOfShareholders></xbrli:xbrl>'


# TCS, 30 Sep 2026 filing (fractions, "_ContextI") and 31 Dec 2021 filing (percents, "I", "Uti")
NEW = _xbrl({"ShareholdingPattern": 1, "ShareholdingOfPromoterAndPromoterGroup": 0.7177, "InstitutionsForeign": 0.0901,
             "InstitutionsDomestic": 0.1357, "MutualFundsOrUTI": 0.0565, "NonInstitutions": 0.0565}, "_ContextI")
OLD = _xbrl({"ShareholdingPattern": 100, "ShareholdingOfPromoterAndPromoterGroup": 72.19, "InstitutionsForeign": 12.68,
             "InstitutionsDomestic": 10.91, "MutualFundsOrUti": 4.32, "NonInstitutions": 4.63}, "I", holders=2_075_117)


def test_new_and_old_filing_formats_give_percent():
    assert parse_pattern_xbrl(NEW) == {"promoter_pct": 71.77, "fii_pct": 9.01, "dii_pct": 13.57, "mf_pct": 5.65,
                                       "retail_pct": 5.65, "shareholders": 2_579_099}
    old = parse_pattern_xbrl(OLD)
    assert old is not None and old["fii_pct"] == 12.68 and old["mf_pct"] == 4.32 and old["shareholders"] == 2_075_117


def test_a_company_without_promoters_still_parses():
    hdfc = _xbrl({"ShareholdingPattern": 1, "InstitutionsForeign": 0.394, "InstitutionsDomestic": 0.4363, "NonInstitutions": 0.1697}, "_ContextI")
    parsed = parse_pattern_xbrl(hdfc)
    assert parsed is not None and parsed["promoter_pct"] is None and parsed["fii_pct"] == 39.4 and parsed["dii_pct"] == 43.63


def test_a_file_without_the_pattern_is_rejected():
    assert parse_pattern_xbrl("<xbrli:xbrl></xbrli:xbrl>") is None


@pytest.mark.asyncio
async def test_endpoint_reads_missing_quarters_once(client, db_session, monkeypatch):
    db_session.add(Shareholding(ticker="TCS.NS", quarter=date(2026, 6, 30), promoter_pct=71.77))
    await db_session.commit()
    history = [
        {"symbol": "TCS", "date": "30-SEP-2026", "pr_and_prgrp": "71.77", "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/SEP.xml"},
        {"symbol": "TCS", "date": "30-JUN-2026", "pr_and_prgrp": "71.77", "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/JUN.xml"},
        {"symbol": "TCS", "date": "30-JUN-2026", "pr_and_prgrp": "71.70", "xbrl": "https://evil.example/old.xml"},  # original, superseded
    ]
    fetched: list[str] = []

    async def nse(path, ttl=0):
        assert path.endswith("symbol=TCS")
        return history

    async def fetch(client, url):
        fetched.append(url)
        return parse_pattern_xbrl(NEW if "SEP" in url else OLD)

    monkeypatch.setattr(nse_market, "nse_json", nse)
    monkeypatch.setattr(shareholding, "_fetch_pattern", fetch)
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/stocks/tcs.ns/shareholding", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [q["quarter"] for q in body] == ["2026-09-30", "2026-06-30"]
    assert body[0]["fii_pct"] == 9.01 and body[1]["fii_pct"] == 12.68 and body[1]["promoter_pct"] == 71.77
    assert sorted(fetched) == ["https://nsearchives.nseindia.com/corporate/xbrl/JUN.xml", "https://nsearchives.nseindia.com/corporate/xbrl/SEP.xml"]

    await client.get("/api/v1/stocks/TCS.NS/shareholding", headers=headers)
    assert len(fetched) == 2  # stored splits aren't read again
    assert (await client.get("/api/v1/stocks/AAPL/shareholding", headers=headers)).status_code == 404
