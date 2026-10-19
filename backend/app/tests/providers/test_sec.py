"""Unit tests for SEC EDGAR data provider."""

import pytest

from app.providers.sec import SECProvider


@pytest.fixture
def sec_provider():
    return SECProvider(user_agent="TestAgent admin@example.com")


@pytest.fixture
def mock_sec_data():
    return {
        "cik": "320193",
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "description": "Amount of total revenue...",
                    "units": {
                        "USD": [
                            {
                                "start": "2022-09-25",
                                "end": "2023-09-30",
                                "val": 383285000000,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "frame": "CY2023",
                            }
                        ]
                    },
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2022-09-25",
                                "end": "2023-09-30",
                                "val": 96995000000,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-09-30",
                                "val": 352583000000,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                            }
                        ]
                    }
                },
            }
        },
    }


def test_get_cik(sec_provider):
    """Test CIK lookup."""
    assert sec_provider.get_cik("AAPL") == "0000320193"
    assert sec_provider.get_cik("MSFT") == "0000789019"
    assert sec_provider.get_cik("UNKNOWN") is None


def test_extract_metrics(sec_provider, mock_sec_data):
    """Test metric extraction from mock data."""
    metrics = sec_provider.extract_metrics(mock_sec_data)

    assert "revenue" in metrics
    assert len(metrics["revenue"]) == 1
    assert metrics["revenue"][0]["val"] == 383285000000

    assert "net_income" in metrics
    assert len(metrics["net_income"]) == 1
    assert metrics["net_income"][0]["val"] == 96995000000

    assert "total_assets" in metrics
    assert metrics["total_assets"][0]["val"] == 352583000000


def test_get_latest_metrics(sec_provider, mock_sec_data):
    """Test latest metric extraction."""
    metrics = sec_provider.extract_metrics(mock_sec_data)
    latest = sec_provider.get_latest_metrics(metrics)

    assert latest["revenue"] == 383285000000
    assert latest["net_income"] == 96995000000
    assert latest["total_assets"] == 352583000000
    assert latest["total_debt"] is None


def test_normalize_values_sorting(sec_provider):
    """Test that values are sorted by end date."""
    concepts = {
        "Revenues": {
            "units": {"USD": [{"end": "2023-09-30", "val": 200}, {"end": "2022-09-30", "val": 100}]}
        }
    }
    normalized = sec_provider._normalize_values(concepts, ["Revenues"])
    assert len(normalized) == 2
    assert normalized[0]["end"] == "2022-09-30"
    assert normalized[1]["end"] == "2023-09-30"


@pytest.mark.asyncio
async def test_get_cik_async_static(sec_provider):
    """Test async CIK resolution from default static cache."""
    cik = await sec_provider.get_cik_async("AAPL")
    assert cik == "0000320193"


@pytest.mark.asyncio
async def test_load_company_tickers_dynamic_success(sec_provider, monkeypatch):
    """Test dynamic ingestion of company_tickers.json from SEC EDGAR."""
    from unittest.mock import AsyncMock, MagicMock
    import httpx

    mock_sec_directory = {
        "0": {"cik_str": 200406, "ticker": "JNJ", "title": "Johnson & Johnson"},
        "1": {"cik_str": 1067983, "ticker": "BRK.A", "title": "BERKSHIRE HATHAWAY INC"},
        "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_sec_directory
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: mock_client)

    tickers = await sec_provider.load_company_tickers(force_refresh=True)

    assert "JNJ" in tickers
    assert tickers["JNJ"] == "0000200406"
    assert "BRK.A" in tickers
    assert "BRK-A" in tickers
    assert tickers["BRK.A"] == "0001067983"

    # Verify get_cik_async resolves newly ingested ticker
    assert await sec_provider.get_cik_async("JNJ") == "0000200406"
    # Verify sync get_cik also resolves from updated memory cache
    assert sec_provider.get_cik("JNJ") == "0000200406"


@pytest.mark.asyncio
async def test_load_company_tickers_network_error_fallback(sec_provider, monkeypatch):
    """Test graceful fallback to static CIK mapping when SEC network fails."""
    from unittest.mock import AsyncMock
    import httpx

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectTimeout("SEC EDGAR timeout")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: mock_client)

    tickers = await sec_provider.load_company_tickers(force_refresh=True)

    # Should not raise exception and should preserve static fallback tickers
    assert "AAPL" in tickers
    assert tickers["AAPL"] == "0000320193"
    assert await sec_provider.get_cik_async("UNKNOWN_TICKER") is None

