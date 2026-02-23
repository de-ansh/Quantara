import pytest
from unittest.mock import patch, MagicMock
from app.providers.sec import SECProvider

MOCK_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0306</schemaVersion>
    <documentType>4</documentType>
    <issuer>
        <issuerCik>0000320193</issuerCik>
        <issuerName>Apple Inc.</issuerName>
        <issuerTradingSymbol>AAPL</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>1234567890</rptOwnerCik>
            <rptOwnerName>Tim Cook</rptOwnerName>
        </reportingOwnerId>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <transactionDate>
                <value>2023-10-01</value>
            </transactionDate>
            <transactionCoding>
                <transactionCode>S</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>5000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>175.50</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>D</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <transactionDate>
                <value>2023-10-02</value>
            </transactionDate>
            <transactionCoding>
                <transactionCode>P</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>1000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>170.00</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>A</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <transactionDate>
                <value>2023-10-03</value>
            </transactionDate>
            <transactionCoding>
                <transactionCode>M</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>2000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>150.00</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>A</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
"""

class TestSECProviderForm4:
    def test_parse_form4_xml(self):
        provider = SECProvider()
        transactions = provider.parse_form4_xml(MOCK_FORM4_XML)
        
        assert len(transactions) == 3
        
        # Sell transaction
        tx1 = transactions[0]
        assert tx1["reporting_owner"] == "Tim Cook"
        assert tx1["transaction_date"] == "2023-10-01"
        assert tx1["transaction_type"] == "S"
        assert tx1["shares"] == 5000.0
        assert tx1["price_per_share"] == 175.50
        assert tx1["acquired_disposed"] == "D"
        assert tx1["classification"] == "Sell"
        
        # Buy transaction
        tx2 = transactions[1]
        assert tx2["transaction_date"] == "2023-10-02"
        assert tx2["transaction_type"] == "P"
        assert tx2["shares"] == 1000.0
        assert tx2["classification"] == "Buy"
        
        # Neutral transaction
        tx3 = transactions[2]
        assert tx3["transaction_date"] == "2023-10-03"
        assert tx3["transaction_type"] == "M"
        assert tx3["classification"] == "Neutral"

    @pytest.mark.asyncio
    @patch("app.providers.sec.httpx.AsyncClient.get")
    async def test_fetch_insider_transactions_success(self, mock_get):
        provider = SECProvider()
        
        # Mock the responses
        # Call 1: submissions JSON
        mock_resp_submissions = MagicMock()
        mock_resp_submissions.status_code = 200
        mock_resp_submissions.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["4", "8-K"],
                    "accessionNumber": ["0001-23-0001", "0002-23-0002"],
                    "primaryDocument": ["doc1.xml", "doc2.htm"]
                }
            }
        }
        
        # Call 2: index JSON
        mock_resp_index = MagicMock()
        mock_resp_index.status_code = 200
        mock_resp_index.json.return_value = {
            "directory": {
                "item": [
                    {"name": "wk-form4.xml"}
                ]
            }
        }
        
        # Call 3: Form 4 XML
        mock_resp_xml = MagicMock()
        mock_resp_xml.status_code = 200
        mock_resp_xml.text = MOCK_FORM4_XML
        
        mock_get.side_effect = [mock_resp_submissions, mock_resp_index, mock_resp_xml]
        
        transactions = await provider.fetch_insider_transactions("AAPL", limit=1)
        
        assert len(transactions) == 3
        assert transactions[0]["classification"] == "Sell"
        assert mock_get.call_count == 3
