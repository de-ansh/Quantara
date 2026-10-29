"""SEC EDGAR data provider using Company Facts API."""

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Row of an EDGAR filing index whose document type is the press-release exhibit
_EX99_ROW = re.compile(r'<a href="([^"]+\.html?)">[^<]*</a></td>\s*<td[^>]*>\s*EX-99\.1\s*</td>', re.I)
EARNINGS_RELEASE_MAX_CHARS = 30_000


class _TextExtractor(HTMLParser):
    """Visible text of an HTML document (scripts and styles dropped)."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return re.sub(r"\s+", " ", " ".join(extractor.parts)).strip()


class SECProvider:
    """
    SEC EDGAR data provider.

    Fetches structured XBRL data from the SEC Company Facts API.
    Ref: https://data.sec.gov/api/xbrl/companyfacts/CIK########.json
    """

    BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"

    # Common XBRL tags for financial metrics
    TAG_MAPPINGS = {
        "revenue": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "TotalRevenuesAndOtherIncome",
        ],
        "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
        "total_assets": ["Assets"],
        # Values from all tags are merged and sorted by period end; for equal end dates the
        # last-listed tag wins, so the most common total (LongTermDebt) goes last.
        "total_debt": [
            "DebtAndCapitalLeaseObligations",
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebt",
        ],
        "total_equity": ["StockholdersEquity"],
        "cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "shares_outstanding": [
            "EntityCommonStockSharesOutstanding",
            "WeightedAverageNumberOfSharesOutstandingBasic",
        ],
        "eps": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
    }

    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    # Hardcoded CIK mapping for initial set of companies / offline fallback
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

    def __init__(self, user_agent: str | None = None):
        """Initialize the SEC provider."""
        self.user_agent = user_agent or settings.sec_user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self._cik_cache: dict[str, str] = dict(self.CIK_MAPPING)
        self._cache_timestamp: float = 0.0
        self._cache_ttl_seconds: float = 86400.0  # 24 hours

    async def load_company_tickers(self, force_refresh: bool = False) -> dict[str, str]:
        """
        Fetch official SEC ticker-to-CIK directory from company_tickers.json.

        Caches results in memory with 24h TTL. Falls back to static CIK_MAPPING on error.
        """
        import time

        now = time.time()
        if (
            not force_refresh
            and (now - self._cache_timestamp) < self._cache_ttl_seconds
            and len(self._cik_cache) > len(self.CIK_MAPPING)
        ):
            return self._cik_cache

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Loading dynamic SEC company tickers from {self.TICKERS_URL}")
                response = await client.get(self.TICKERS_URL, headers=headers, timeout=15.0)
                response.raise_for_status()
                data = response.json()

                entries: list[Any]
                if isinstance(data, dict):
                    entries = list(data.values())
                elif isinstance(data, list):
                    entries = data
                else:
                    entries = []

                new_cache: dict[str, str] = dict(self.CIK_MAPPING)
                for entry in entries:
                    if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry:
                        t = str(entry["ticker"]).strip().upper()
                        c = str(entry["cik_str"]).strip().zfill(10)
                        new_cache[t] = c
                        if "." in t:
                            new_cache[t.replace(".", "-")] = c
                        elif "-" in t:
                            new_cache[t.replace("-", ".")] = c

                if len(new_cache) > len(self.CIK_MAPPING):
                    self._cik_cache = new_cache
                    self._cache_timestamp = now
                    logger.info(f"Loaded {len(self._cik_cache)} dynamic SEC CIK company mappings")

        except Exception as e:
            logger.warning(
                f"Failed to fetch dynamic company_tickers.json from SEC ({e}), falling back to static CIK mapping"
            )

        return self._cik_cache

    async def get_cik_async(self, ticker: str) -> str | None:
        """
        Asynchronously resolve 10-digit CIK for a ticker, loading SEC directory if needed.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            10-digit CIK string or None.
        """
        t = ticker.upper()
        if t.endswith(".NS") or t.endswith(".BO") or ".NS" in t or ".BO" in t:
            return None
        if t in self._cik_cache:
            return self._cik_cache[t]

        # Cache miss: attempt dynamic directory ingestion
        await self.load_company_tickers()
        return self._cik_cache.get(t)

    def get_cik(self, ticker: str) -> str | None:
        """
        Get 10-digit CIK for a ticker synchronously.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            10-digit CIK string or None.
        """
        t = ticker.upper()
        if t.endswith(".NS") or t.endswith(".BO") or ".NS" in t or ".BO" in t:
            return None
        cik = self._cik_cache.get(t) or self.CIK_MAPPING.get(t)
        if cik:
            return cik.zfill(10)
        return None

    async def fetch_company_facts(self, ticker: str) -> dict[str, Any] | None:
        """
        Fetch company facts from SEC API.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Raw JSON data or None.
        """
        if ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO"):
            return None

        cik = await self.get_cik_async(ticker)
        if not cik:
            logger.info(f"CIK not applicable or found for ticker {ticker}")
            return None

        url = f"{self.BASE_URL}/CIK{cik}.json"

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Fetching SEC data for {ticker} (CIK: {cik})")
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching SEC data for {ticker}: {e.response.status_code}")
                return None
            except Exception as e:
                logger.error(f"Error fetching SEC data for {ticker}: {e}")
                return None

    def _normalize_values(self, concepts: dict[str, Any], tags: list[str]) -> list[dict[str, Any]]:
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
                for _unit_name, values in units.items():
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
                            "frame": val.get("frame"),
                        }
                        all_data.append(period_data)

                # If we found data for a tag, we might want to prefer it,
                # but for simplicity, we combine and could deduplicate later if needed.
                # In practice, SEC data has many overlaps.

        # Sort by end date
        all_data.sort(key=lambda x: x["end"] if x["end"] else "")
        return all_data

    def extract_metrics(self, data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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

    def get_latest_metrics(self, metrics: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
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

    def parse_form4_xml(self, xml_content: str) -> list[dict[str, Any]]:
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
            xml_txs = root.findall(".//nonDerivativeTransaction") + root.findall(
                ".//derivativeTransaction"
            )

            for tx in xml_txs:
                # Date
                date_node = tx.find(".//transactionDate/value")
                tx_date = (
                    date_node.text.strip() if date_node is not None and date_node.text else None
                )

                # Transaction Code
                code_node = tx.find(".//transactionCoding/transactionCode")
                tx_code = (
                    code_node.text.strip()
                    if code_node is not None and code_node.text
                    else "Unknown"
                )

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
                ad_code = (
                    ad_node.text.strip() if ad_node is not None and ad_node.text else "Unknown"
                )

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

                transactions.append(
                    {
                        "reporting_owner": owner_name,
                        "transaction_date": tx_date,
                        "transaction_type": tx_code,
                        "shares": shares,
                        "price_per_share": price,
                        "acquired_disposed": ad_code,
                        "classification": classification,
                    }
                )
        except ET.ParseError as e:
            logger.error(f"Error parsing Form 4 XML: {e}")

        return transactions

    async def fetch_latest_earnings_release(self, ticker: str) -> dict[str, Any] | None:
        """Latest earnings press release (8-K Item 2.02, Exhibit 99.1) as text; None if unavailable."""
        cik = await self.get_cik_async(ticker)
        if not cik:
            return None
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            try:
                resp = await client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
                resp.raise_for_status()
                recent = resp.json().get("filings", {}).get("recent", {})
                filing = next(
                    (
                        (accn, filed)
                        for form, items, accn, filed in zip(
                            recent.get("form", []), recent.get("items", []),
                            recent.get("accessionNumber", []), recent.get("filingDate", []),
                            strict=False,
                        )
                        if form == "8-K" and "2.02" in (items or "")
                    ),
                    None,
                )
                if filing is None:
                    return None
                accn, filed = filing
                base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"
                index = await client.get(f"{base}/{accn}-index.htm")
                index.raise_for_status()
                match = _EX99_ROW.search(index.text)
                if not match:
                    return None
                url = f"https://www.sec.gov{match.group(1)}"
                page = await client.get(url)
                page.raise_for_status()
            except (httpx.HTTPError, ValueError) as e:
                logger.warning(f"Earnings release lookup failed for {ticker}: {e}")
                return None
        text = html_to_text(page.text)
        if len(text) < 500:  # an exhibit this short is a cover page, not the release
            return None
        return {"date": filed, "url": url, "text": text[:EARNINGS_RELEASE_MAX_CHARS]}

    async def fetch_insider_transactions(self, ticker: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Fetch recent Form 4 insider transactions for a given ticker.

        Args:
            ticker: Stock ticker symbol.
            limit: Number of recent Form 4 filings to process.

        Returns:
            List of parsed and classified insider transactions.
        """
        if ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO"):
            return []

        cik = await self.get_cik_async(ticker)
        if not cik:
            logger.info(f"CIK not applicable or found for ticker {ticker}")
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

    def parse_form13f_xml(self, xml_content: str) -> list[dict[str, Any]]:
        """
        Parse SEC Form 13F Information Table XML to extract institutional holdings.

        Args:
            xml_content: Raw XML string of Form 13F Information Table.

        Returns:
            List of structured institutional holding records.
        """
        holdings = []
        try:
            root = ET.fromstring(xml_content)

            def _find_text(element: ET.Element, local_tag: str) -> str | None:
                for child in element.iter():
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if tag.lower() == local_tag.lower() and child.text:
                        return child.text.strip()
                return None

            # Find all infoTable elements regardless of XML namespace
            info_tables = []
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag.lower() == "infotable":
                    info_tables.append(elem)

            for table in info_tables:
                issuer = _find_text(table, "nameOfIssuer") or "Unknown"
                title_class = _find_text(table, "titleOfClass") or "COM"
                cusip = _find_text(table, "cusip") or ""

                # Value
                val_text = _find_text(table, "value")
                value = 0.0
                if val_text:
                    try:
                        value = float(val_text.replace(",", ""))
                    except ValueError:
                        pass

                # Shares / Principal Amount
                shares_text = _find_text(table, "sshPrnamt")
                shares = 0.0
                if shares_text:
                    try:
                        shares = float(shares_text.replace(",", ""))
                    except ValueError:
                        pass

                share_type = _find_text(table, "sshPrnamtType") or "SH"
                put_call = _find_text(table, "putCall")
                investment_discretion = _find_text(table, "investmentDiscretion") or "SOLE"

                # Voting authority
                voting_auth = {"sole": 0.0, "shared": 0.0, "none": 0.0}
                for child in table.iter():
                    c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    c_tag_lower = c_tag.lower()
                    if c_tag_lower in ("sole", "shared", "none") and child.text:
                        try:
                            voting_auth[c_tag_lower] = float(child.text.strip().replace(",", ""))
                        except ValueError:
                            pass

                holdings.append(
                    {
                        "name_of_issuer": issuer.upper(),
                        "title_of_class": title_class.upper(),
                        "cusip": cusip.upper(),
                        "value": value,
                        "shares": shares,
                        "share_type": share_type.upper(),
                        "put_call": put_call.upper() if put_call else None,
                        "investment_discretion": investment_discretion.upper(),
                        "voting_authority": voting_auth,
                    }
                )

        except ET.ParseError as e:
            logger.error(f"Error parsing Form 13F XML: {e}")

        return holdings

    def detect_institutional_accumulation(
        self,
        previous_holdings: list[dict[str, Any]],
        current_holdings: list[dict[str, Any]],
        min_increase_pct: float = 5.0,
    ) -> list[dict[str, Any]]:
        """
        Detect significant quarter-over-quarter institutional accumulation across holdings.

        Args:
            previous_holdings: List of holdings from previous quarter Form 13F.
            current_holdings: List of holdings from current quarter Form 13F.
            min_increase_pct: Minimum percentage increase in shares to qualify as accumulation.

        Returns:
            List of accumulated positions sorted by percentage change descending.
        """
        prev_by_cusip: dict[str, dict[str, Any]] = {}
        prev_by_name: dict[str, dict[str, Any]] = {}

        for h in previous_holdings:
            cusip = h.get("cusip", "").strip()
            name = h.get("name_of_issuer", "").strip()
            if cusip:
                prev_by_cusip[cusip] = h
            if name:
                prev_by_name[name] = h

        accumulations = []

        for curr in current_holdings:
            cusip = curr.get("cusip", "").strip()
            name = curr.get("name_of_issuer", "").strip()
            current_shares = float(curr.get("shares") or 0.0)
            current_value = float(curr.get("value") or 0.0)

            if current_shares <= 0:
                continue

            prev = None
            if cusip and cusip in prev_by_cusip:
                prev = prev_by_cusip[cusip]
            elif name and name in prev_by_name:
                prev = prev_by_name[name]

            if prev is None:
                # Brand new position entered this quarter
                accumulations.append(
                    {
                        "name_of_issuer": name,
                        "title_of_class": curr.get("title_of_class", "COM"),
                        "cusip": cusip,
                        "previous_shares": 0.0,
                        "current_shares": current_shares,
                        "share_change": current_shares,
                        "change_pct": 100.0,
                        "previous_value": 0.0,
                        "current_value": current_value,
                        "value_change": current_value,
                        "is_new_position": True,
                        "is_accumulation": True,
                    }
                )
            else:
                prev_shares = float(prev.get("shares") or 0.0)
                prev_value = float(prev.get("value") or 0.0)

                if prev_shares > 0:
                    share_delta = current_shares - prev_shares
                    change_pct = (share_delta / prev_shares) * 100.0

                    if change_pct >= min_increase_pct:
                        accumulations.append(
                            {
                                "name_of_issuer": name,
                                "title_of_class": curr.get("title_of_class", "COM"),
                                "cusip": cusip,
                                "previous_shares": prev_shares,
                                "current_shares": current_shares,
                                "share_change": share_delta,
                                "change_pct": round(change_pct, 2),
                                "previous_value": prev_value,
                                "current_value": current_value,
                                "value_change": current_value - prev_value,
                                "is_new_position": False,
                                "is_accumulation": True,
                            }
                        )

        accumulations.sort(key=lambda x: x["change_pct"], reverse=True)
        return accumulations

    async def fetch_13f_holdings(
        self, manager_cik: str, limit: int = 2
    ) -> list[dict[str, Any]]:
        """
        Fetch recent Form 13F institutional holdings filings for an institutional manager CIK.

        Args:
            manager_cik: 10-digit CIK of the institutional investment manager.
            limit: Number of recent 13F filings to process (e.g. 2 for QoQ comparison).

        Returns:
            List of parsed filings with metadata and holdings list.
        """
        cik = str(manager_cik).strip().zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        filing_batches = []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                if "filings" not in data or "recent" not in data["filings"]:
                    return []

                recent = data["filings"]["recent"]
                forms = recent.get("form", [])
                accns = recent.get("accessionNumber", [])
                filing_dates = recent.get("filingDate", [])
                report_dates = recent.get("reportDate", [])

                indices = [i for i, f in enumerate(forms) if f in ("13F-HR", "13F-HR/A")]

                processed = 0
                for idx in indices:
                    if processed >= limit:
                        break

                    accn = accns[idx]
                    accn_nodash = accn.replace("-", "")
                    cik_nopad = str(int(cik))
                    filing_date = filing_dates[idx] if idx < len(filing_dates) else None
                    report_date = report_dates[idx] if idx < len(report_dates) else None

                    idx_url = f"https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accn_nodash}/index.json"
                    idx_resp = await client.get(idx_url, headers=self.headers, timeout=10.0)
                    if idx_resp.status_code != 200:
                        continue

                    idx_data = idx_resp.json()

                    xml_filename = None
                    for item in idx_data.get("directory", {}).get("item", []):
                        name = item.get("name", "")
                        if name.endswith(".xml") and not name.endswith("_htm.xml"):
                            if "infotable" in name.lower() or "13f" in name.lower():
                                xml_filename = name
                                break
                            elif xml_filename is None:
                                xml_filename = name

                    if xml_filename:
                        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_nopad}/{accn_nodash}/{xml_filename}"
                        xml_resp = await client.get(xml_url, headers=self.headers, timeout=10.0)
                        if xml_resp.status_code == 200:
                            holdings = self.parse_form13f_xml(xml_resp.text)
                            filing_batches.append(
                                {
                                    "manager_cik": cik,
                                    "accession_number": accn,
                                    "filing_date": filing_date,
                                    "report_date": report_date,
                                    "holdings_count": len(holdings),
                                    "holdings": holdings,
                                }
                            )
                            processed += 1

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching 13F filings for manager {manager_cik}: {e}")
            except Exception as e:
                logger.error(f"Error fetching 13F filings for manager {manager_cik}: {e}")

        return filing_batches

