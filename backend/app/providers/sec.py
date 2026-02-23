"""SEC EDGAR data provider using Company Facts API."""
import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class SECProvider:
    """
    SEC EDGAR data provider.
    
    Fetches structured XBRL data from the SEC Company Facts API.
    Ref: https://data.sec.gov/api/xbrl/companyfacts/CIK########.json
    """

    BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
    
    # Common XBRL tags for financial metrics
    TAG_MAPPINGS = {
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "TotalRevenuesAndOtherIncome"],
        "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
        "total_assets": ["Assets"],
        "total_debt": ["DebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligations"],
        "cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "shares_outstanding": ["EntityCommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"]
    }

    # Hardcoded CIK mapping for initial set of companies
    CIK_MAPPING = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
        "GOOGL": "0001652045",
        "GOOG": "0001652045",
        "AMZN": "0001018724",
        "TSLA": "0001318605",
        "META": "0001326801",
        "NVDA": "0001045810",
    }

    def __init__(self, user_agent: Optional[str] = None):
        """Initialize the SEC provider."""
        self.user_agent = user_agent or settings.sec_user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"
        }

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get 10-digit CIK for a ticker.
        
        Args:
            ticker: Stock ticker symbol.
            
        Returns:
            10-digit CIK string or None.
        """
        cik = self.CIK_MAPPING.get(ticker.upper())
        if cik:
            return cik.zfill(10)
        return None

    async def fetch_company_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company facts from SEC API.
        
        Args:
            ticker: Stock ticker symbol.
            
        Returns:
            Raw JSON data or None.
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.error(f"CIK not found for ticker {ticker}")
            return None

        url = f"{self.BASE_URL}/CIK{cik}.json"
        
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Fetching SEC data for {ticker} (CIK: {cik})")
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching SEC data for {ticker}: {e.response.status_code}")
                return None
            except Exception as e:
                logger.error(f"Error fetching SEC data for {ticker}: {e}")
                return None

    def _normalize_values(self, concepts: Dict[str, Any], tags: List[str]) -> List[Dict[str, Any]]:
        """
        Extract and normalize values for a given set of tags.
        
        Args:
            concepts: 'us-gaap' concepts from SEC response.
            tags: List of XBRL tags to look for.
            
        Returns:
            List of normalized period data.
        """
        all_data = []
        
        for tag in tags:
            if tag in concepts:
                units = concepts[tag].get("units", {})
                # Usually USD or shares
                for unit_name, values in units.items():
                    for val in values:
                        # Normalize period
                        period_data = {
                            "start": val.get("start"),
                            "end": val.get("end"),
                            "val": val.get("val"),
                            "accn": val.get("accn"),
                            "fy": val.get("fy"),
                            "fp": val.get("fp"),
                            "form": val.get("form"),
                            "filed": val.get("filed"),
                            "frame": val.get("frame")
                        }
                        all_data.append(period_data)
                
                # If we found data for a tag, we might want to prefer it, 
                # but for simplicity, we combine and could deduplicate later if needed.
                # In practice, SEC data has many overlaps.
        
        # Sort by end date
        all_data.sort(key=lambda x: x["end"] if x["end"] else "")
        return all_data

    def extract_metrics(self, data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract key metrics from raw SEC facts data.
        
        Args:
            data: Raw JSON data from SEC API.
            
        Returns:
            Structured dictionary of metrics.
        """
        if not data or "facts" not in data:
            return {}

        us_gaap = data["facts"].get("us-gaap", {})
        dei = data["facts"].get("dei", {})
        
        metrics = {}
        
        # Merge relevant concepts
        concepts = {**us_gaap, **dei}
        
        for metric_name, tags in self.TAG_MAPPINGS.items():
            metrics[metric_name] = self._normalize_values(concepts, tags)
            
        return metrics

    def get_latest_metrics(self, metrics: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Extract the latest values for each metric.
        
        Args:
            metrics: Structured dictionary of metrics from extract_metrics.
            
        Returns:
            Dictionary with latest values.
        """
        latest = {}
        for name, values in metrics.items():
            if values:
                # Assuming the last one is the latest after sorting
                latest[name] = values[-1]["val"]
            else:
                latest[name] = None
        return latest

    def parse_form4_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parse SEC Form 4 XML to extract insider transactions.
        
        Args:
            xml_content: Raw XML string of Form 4.
            
        Returns:
            List of structured transactions.
        """
        transactions = []
        try:
            root = ET.fromstring(xml_content)
            
            # Extract reporting owner
            owner_name = "Unknown"
            owner = root.find(".//reportingOwnerId/rptOwnerName")
            if owner is not None and owner.text:
                owner_name = owner.text.strip()
                
            # Parse non-derivative and derivative transactions
            xml_txs = root.findall(".//nonDerivativeTransaction") + root.findall(".//derivativeTransaction")
            
            for tx in xml_txs:
                # Date
                date_node = tx.find(".//transactionDate/value")
                tx_date = date_node.text.strip() if date_node is not None and date_node.text else None
                
                # Transaction Code
                code_node = tx.find(".//transactionCoding/transactionCode")
                tx_code = code_node.text.strip() if code_node is not None and code_node.text else "Unknown"
                
                # Shares
                shares_node = tx.find(".//transactionShares/value")
                shares = 0.0
                if shares_node is not None and shares_node.text:
                    try:
                        shares = float(shares_node.text.strip())
                    except ValueError:
                        pass
                
                # Acquired/Disposed code
                ad_node = tx.find(".//transactionAcquiredDisposedCode/value")
                ad_code = ad_node.text.strip() if ad_node is not None and ad_node.text else "Unknown"
                
                # Price per share
                price_node = tx.find(".//transactionPricePerShare/value")
                price = None
                if price_node is not None and price_node.text:
                    try:
                        price = float(price_node.text.strip())
                    except ValueError:
                        pass
                
                # Classification logic
                # P = Purchase, S = Sale
                # M = Exercised/converted (Neutral/Buy depending on interpretation, typically neutral or acquisition)
                # F = Withholding for tax (Neutral/Sell)
                # A = Grant, award, or other acquisition (Neutral typically, though 'A' is used as Acquired/Disposed code too)
                classification = "Neutral"
                if tx_code == "P":
                    classification = "Buy"
                elif tx_code == "S":
                    classification = "Sell"
                else:
                    # Fallback to AD code if explicit
                    # But grants are usually AD code 'A' and code 'A'. 
                    # If it's a purchase 'P' it is AD code 'A'.
                    # If it's a sale 'S' it is AD code 'D'.
                    # We will stick to strictly P=Buy, S=Sell, others=Neutral.
                    pass
                
                transactions.append({
                    "reporting_owner": owner_name,
                    "transaction_date": tx_date,
                    "transaction_type": tx_code,
                    "shares": shares,
                    "price_per_share": price,
                    "acquired_disposed": ad_code,
                    "classification": classification
                })
        except ET.ParseError as e:
            logger.error(f"Error parsing Form 4 XML: {e}")
            
        return transactions

    async def fetch_insider_transactions(self, ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch recent Form 4 insider transactions for a given ticker.
        
        Args:
            ticker: Stock ticker symbol.
            limit: Number of recent Form 4 filings to process.
            
        Returns:
            List of parsed and classified insider transactions.
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.error(f"CIK not found for ticker {ticker}")
            return []

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        all_transactions = []
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. Fetch recent filings
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                if "filings" not in data or "recent" not in data["filings"]:
                    return []
                    
                recent = data["filings"]["recent"]
                forms = recent.get("form", [])
                accns = recent.get("accessionNumber", [])
                
                # 2. Find Form 4 indices
                form4_indices = [i for i, f in enumerate(forms) if f == "4"]
                
                # 3. Process up to `limit` Form 4s
                processed = 0
                for idx in form4_indices:
                    if processed >= limit:
                        break
                        
                    accn = accns[idx]
                    accn_nodash = accn.replace("-", "")
                    cik_nopad = str(int(cik))
                    
                    # 4. Fetch the directory index for this accession number
                    idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accn_nodash}/index.json"
                    idx_resp = await client.get(idx_url, headers=self.headers, timeout=10.0)
                    if idx_resp.status_code != 200:
                        continue
                        
                    idx_data = idx_resp.json()
                    
                    # 5. Find the raw xml file
                    xml_filename = None
                    for item in idx_data.get("directory", {}).get("item", []):
                        name = item.get("name", "")
                        # Look for pure XML file (not _htm.xml or xml-styled html)
                        if name.endswith(".xml") and not name.endswith("_htm.xml"):
                            xml_filename = name
                            break
                            
                    if xml_filename:
                        # 6. Fetch raw XML and parse
                        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accn_nodash}/{xml_filename}"
                        xml_resp = await client.get(xml_url, headers=self.headers, timeout=10.0)
                        if xml_resp.status_code == 200:
                            txs = self.parse_form4_xml(xml_resp.text)
                            all_transactions.extend(txs)
                            processed += 1
                            
            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching insider transactions for {ticker}: {e}")
            except Exception as e:
                logger.error(f"Error fetching insider transactions for {ticker}: {e}")
                
        return all_transactions
