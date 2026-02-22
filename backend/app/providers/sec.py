"""SEC EDGAR data provider using Company Facts API."""
import asyncio
import json
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
