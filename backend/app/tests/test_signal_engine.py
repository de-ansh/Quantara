import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.signal import Signal as DBSignal
from app.models.stock import Stock
from app.services.signal_engine import (
    Signal,
    SignalEngine,
    SignalType,
    run_periodic_signal_processing,
    save_signal_to_db,
)


@pytest.fixture
def sample_signal():
    return Signal(
        ticker="AAPL",
        signal_type=SignalType.INSIDER_BUYING,
        strength=80.0,
        confidence=90.0,
        timestamp=datetime.utcnow(),
        metadata={"num_insiders": 3, "net_buying": 1000000.0},
    )


@pytest.mark.asyncio
async def test_save_signal_to_db(db_session, sample_signal):
    # Ensure stock is clean/exists
    # 1. Run save helper
    await save_signal_to_db(db_session, sample_signal)

    # 2. Verify signal saved
    stmt = select(DBSignal).where(DBSignal.ticker == "AAPL")
    result = await db_session.execute(stmt)
    sig = result.scalar_one_or_none()
    assert sig is not None
    assert sig.signal_type == "insider_buying"
    assert sig.strength == 80.0
    assert sig.data["num_insiders"] == 3

    # 3. Verify stock was automatically created as foreign key dependency
    stmt_stock = select(Stock).where(Stock.ticker == "AAPL")
    res_stock = await db_session.execute(stmt_stock)
    stock = res_stock.scalar_one_or_none()
    assert stock is not None
    assert stock.ticker == "AAPL"


def test_detect_sentiment_spike():
    engine = SignalEngine()
    
    # Valid spike: sentiment change >= 0.2 and mentions >= 100
    sig = engine.detect_sentiment_spike(
        ticker="NVDA",
        current_sentiment=0.75,
        baseline_sentiment=0.10,
        mention_volume=250,
    )
    assert sig is not None
    assert sig.signal_type == SignalType.SENTIMENT_SPIKE
    assert sig.ticker == "NVDA"
    assert sig.strength > 0
    assert sig.metadata["mention_volume"] == 250
    assert sig.metadata["sentiment_change"] == pytest.approx(0.65)

    # Rejection: insufficient sentiment change (< 0.2)
    sig_low_delta = engine.detect_sentiment_spike(
        ticker="NVDA",
        current_sentiment=0.25,
        baseline_sentiment=0.15,
        mention_volume=250,
    )
    assert sig_low_delta is None

    # Rejection: insufficient mention volume (< 100)
    sig_low_vol = engine.detect_sentiment_spike(
        ticker="NVDA",
        current_sentiment=0.80,
        baseline_sentiment=0.10,
        mention_volume=50,
    )
    assert sig_low_vol is None


def test_detect_institutional_buying():
    engine = SignalEngine()

    # Valid institutional buying: >= 2.0% change and >= 3 institutions
    sig = engine.detect_institutional_buying(
        ticker="MSFT",
        institutional_ownership_change=4.2,
        num_institutions_buying=5,
    )
    assert sig is not None
    assert sig.signal_type == SignalType.INSTITUTIONAL_BUYING
    assert sig.ticker == "MSFT"
    assert sig.metadata["ownership_change_pct"] == 4.2
    assert sig.metadata["num_institutions"] == 5

    # Rejection: low ownership change (< 2.0%)
    sig_low_change = engine.detect_institutional_buying(
        ticker="MSFT",
        institutional_ownership_change=1.2,
        num_institutions_buying=5,
    )
    assert sig_low_change is None

    # Rejection: few institutions (< 3)
    sig_few_inst = engine.detect_institutional_buying(
        ticker="MSFT",
        institutional_ownership_change=5.0,
        num_institutions_buying=2,
    )
    assert sig_few_inst is None


def test_compute_financial_sentiment():
    from app.services.signal_engine import compute_financial_sentiment

    # Positive headline
    pos_score = compute_financial_sentiment(["NVIDIA surges to record profit with dividend upgrade"])
    assert pos_score > 0.4

    # Negative headline
    neg_score = compute_financial_sentiment(["Intel drops on revenue miss and investigation lawsuit"])
    assert neg_score < -0.4

    # Empty
    assert compute_financial_sentiment([]) == 0.0


@pytest.mark.asyncio
@patch("asyncio.sleep")
@patch("app.providers.sec.SECProvider.fetch_insider_transactions")
@patch("app.providers.sec.SECProvider.fetch_company_facts")
@patch("app.providers.yahoo.YahooFinanceProvider.get_stock_news")
@patch("app.providers.yahoo.YahooFinanceProvider.get_institutional_ownership")
async def test_run_periodic_signal_processing(
    mock_inst_ownership, mock_news, mock_facts, mock_txs, mock_sleep, db_session
):
    # Setup mocks
    mock_txs.return_value = [
        {
            "reporting_owner": "Tim Cook",
            "transaction_date": "2023-10-01",
            "transaction_type": "P",
            "shares": 10000.0,
            "price_per_share": 150.0,
            "acquired_disposed": "A",
            "classification": "Buy",
        },
        {
            "reporting_owner": "Luca Maestri",
            "transaction_date": "2023-10-02",
            "transaction_type": "P",
            "shares": 5000.0,
            "price_per_share": 150.0,
            "acquired_disposed": "A",
            "classification": "Buy",
        },
    ]
    mock_facts.return_value = {
        "facts": {
            "us-gaap": {
                "EarningsPerShareBasic": {
                    "units": {
                        "USD/shares": [
                            {"val": 1.5, "form": "10-Q", "end": "2023-09-30", "filed": "2023-10-15"}
                        ]
                    }
                }
            }
        }
    }
    mock_news.return_value = [
        {"title": "Apple surges on record profit and bullish guidance"},
        {"title": "Strong growth beats estimates as Apple expands partnership"},
        {"title": "Dividend upgrade and record revenue rally shares"},
        {"title": "Apple outperformance continues with strong innovation"},
    ]
    mock_inst_ownership.return_value = {
        "ownership_pct": 65.0,
        "ownership_change_pct": 3.8,
        "num_institutions": 1500,
        "num_institutions_buying": 8,
    }

    # Force periodic task to raise CancelledError after first execution
    mock_sleep.side_effect = asyncio.CancelledError()

    # Patch database session maker to return our test db_session
    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = db_session

    with patch("app.core.database.AsyncSessionLocal", mock_session_local):
        try:
            await run_periodic_signal_processing(interval_seconds=1)
        except asyncio.CancelledError:
            pass

    # Verify all 4 signal types were generated and stored in db
    stmt = select(DBSignal)
    result = await db_session.execute(stmt)
    signals = result.scalars().all()

    assert len(signals) >= 4
    types = [s.signal_type for s in signals]
    assert "insider_buying" in types
    assert "earnings_surprise" in types
    assert "sentiment_spike" in types
    assert "institutional_buying" in types

