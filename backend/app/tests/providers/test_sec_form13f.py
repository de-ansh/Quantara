"""Tests for SEC Form 13F Information Table parsing and institutional accumulation detection."""

from unittest.mock import MagicMock, patch

import pytest

from app.providers.sec import SECProvider

MOCK_FORM13F_XML_NAMESPACED = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
    <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>15423000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>85000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
            <Sole>85000</Sole>
            <Shared>0</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
    <infoTable>
        <nameOfIssuer>MICROSOFT CORP</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>594918104</cusip>
        <value>21500000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>50000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <putCall>CALL</putCall>
        <investmentDiscretion>DEFINED</investmentDiscretion>
        <votingAuthority>
            <Sole>40000</Sole>
            <Shared>10000</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
</informationTable>
"""

MOCK_FORM13F_XML_PLAIN = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable>
    <infoTable>
        <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
        <titleOfClass>COMMON</titleOfClass>
        <cusip>67066G104</cusip>
        <value>35000000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>280000</sshPrnamt>
            <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
            <Sole>280000</Sole>
            <Shared>0</Shared>
            <None>0</None>
        </votingAuthority>
    </infoTable>
</informationTable>
"""


class TestSECProviderForm13F:
    def test_parse_form13f_xml_namespaced(self):
        provider = SECProvider()
        holdings = provider.parse_form13f_xml(MOCK_FORM13F_XML_NAMESPACED)

        assert len(holdings) == 2

        # 1. AAPL holding
        aapl = holdings[0]
        assert aapl["name_of_issuer"] == "APPLE INC"
        assert aapl["title_of_class"] == "COM"
        assert aapl["cusip"] == "037833100"
        assert aapl["value"] == 15423000.0
        assert aapl["shares"] == 85000.0
        assert aapl["share_type"] == "SH"
        assert aapl["put_call"] is None
        assert aapl["investment_discretion"] == "SOLE"
        assert aapl["voting_authority"]["sole"] == 85000.0
        assert aapl["voting_authority"]["shared"] == 0.0

        # 2. MSFT option holding
        msft = holdings[1]
        assert msft["name_of_issuer"] == "MICROSOFT CORP"
        assert msft["cusip"] == "594918104"
        assert msft["put_call"] == "CALL"
        assert msft["investment_discretion"] == "DEFINED"
        assert msft["voting_authority"]["sole"] == 40000.0
        assert msft["voting_authority"]["shared"] == 10000.0

    def test_parse_form13f_xml_plain(self):
        provider = SECProvider()
        holdings = provider.parse_form13f_xml(MOCK_FORM13F_XML_PLAIN)

        assert len(holdings) == 1
        nvda = holdings[0]
        assert nvda["name_of_issuer"] == "NVIDIA CORP"
        assert nvda["cusip"] == "67066G104"
        assert nvda["shares"] == 280000.0
        assert nvda["value"] == 35000000.0

    def test_parse_form13f_xml_malformed(self):
        provider = SECProvider()
        holdings = provider.parse_form13f_xml("<invalid xml content >>>")
        assert holdings == []

    def test_detect_institutional_accumulation(self):
        provider = SECProvider()

        prev_quarter = [
            {"cusip": "037833100", "name_of_issuer": "APPLE INC", "shares": 100000.0, "value": 15000000.0},
            {"cusip": "594918104", "name_of_issuer": "MICROSOFT CORP", "shares": 50000.0, "value": 10000000.0},
            {"cusip": "88160R101", "name_of_issuer": "TESLA INC", "shares": 30000.0, "value": 6000000.0},
        ]

        curr_quarter = [
            # Accumulation: Apple increased by 20%
            {"cusip": "037833100", "name_of_issuer": "APPLE INC", "shares": 120000.0, "value": 19000000.0},
            # Flat/Below threshold: Microsoft increased by only 2%
            {"cusip": "594918104", "name_of_issuer": "MICROSOFT CORP", "shares": 51000.0, "value": 10500000.0},
            # Reduction: Tesla decreased by 10%
            {"cusip": "88160R101", "name_of_issuer": "TESLA INC", "shares": 27000.0, "value": 5400000.0},
            # New position: NVIDIA entered
            {"cusip": "67066G104", "name_of_issuer": "NVIDIA CORP", "shares": 40000.0, "value": 8000000.0},
        ]

        accumulations = provider.detect_institutional_accumulation(
            previous_holdings=prev_quarter,
            current_holdings=curr_quarter,
            min_increase_pct=5.0,
        )

        assert len(accumulations) == 2

        # 1. NVIDIA (New position -> 100% increase)
        nvda = accumulations[0]
        assert nvda["name_of_issuer"] == "NVIDIA CORP"
        assert nvda["is_new_position"] is True
        assert nvda["current_shares"] == 40000.0
        assert nvda["change_pct"] == 100.0

        # 2. Apple (20% increase)
        aapl = accumulations[1]
        assert aapl["name_of_issuer"] == "APPLE INC"
        assert aapl["is_new_position"] is False
        assert aapl["previous_shares"] == 100000.0
        assert aapl["current_shares"] == 120000.0
        assert aapl["share_change"] == 20000.0
        assert aapl["change_pct"] == 20.0
        assert aapl["value_change"] == 4000000.0

    @pytest.mark.asyncio
    async def test_fetch_13f_holdings_mocked(self):
        provider = SECProvider()

        mock_submissions = {
            "filings": {
                "recent": {
                    "form": ["13F-HR", "10-Q"],
                    "accessionNumber": ["0001067983-24-000001", "0001067983-24-000002"],
                    "filingDate": ["2024-02-14", "2024-01-10"],
                    "reportDate": ["2023-12-31", "2023-12-31"],
                }
            }
        }

        mock_index = {
            "directory": {
                "item": [
                    {"name": "primary_doc.html"},
                    {"name": "infotable.xml"},
                ]
            }
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            def side_effect(url, headers=None, timeout=None):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                if "submissions" in url:
                    mock_resp.json.return_value = mock_submissions
                elif "index.json" in url:
                    mock_resp.json.return_value = mock_index
                elif "infotable.xml" in url:
                    mock_resp.text = MOCK_FORM13F_XML_PLAIN
                return mock_resp

            mock_get.side_effect = side_effect

            batches = await provider.fetch_13f_holdings("0001067983", limit=1)

            assert len(batches) == 1
            b = batches[0]
            assert b["accession_number"] == "0001067983-24-000001"
            assert b["filing_date"] == "2024-02-14"
            assert b["report_date"] == "2023-12-31"
            assert b["holdings_count"] == 1
            assert b["holdings"][0]["name_of_issuer"] == "NVIDIA CORP"
