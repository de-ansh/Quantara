import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.signal_engine import Signal, SignalType, save_signal_to_db, run_periodic_signal_processing
from app.models.signal import Signal as DBSignal
from app.models.stock import Stock
from sqlalchemy import select

@pytest.fixture
def sample_signal():
    return Signal(
        ticker="AAPL",
        signal_type=SignalType.INSIDER_BUYING,
        strength=80.0,
        confidence=90.0,
        timestamp=datetime.utcnow(),
        metadata={"num_insiders": 3, "net_buying": 1000000.0}
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

@pytest.mark.asyncio
@patch("asyncio.sleep")
@patch("app.providers.sec.SECProvider.fetch_insider_transactions")
@patch("app.providers.sec.SECProvider.fetch_company_facts")
async def test_run_periodic_signal_processing(mock_facts, mock_txs, mock_sleep, db_session):
    # Setup mocks
    mock_txs.return_value = [
        {
            "reporting_owner": "Tim Cook",
            "transaction_date": "2023-10-01",
            "transaction_type": "P",
            "shares": 10000.0,
            "price_per_share": 150.0,
            "acquired_disposed": "A",
            "classification": "Buy"
        },
        {
            "reporting_owner": "Luca Maestri",
            "transaction_date": "2023-10-02",
            "transaction_type": "P",
            "shares": 5000.0,
            "price_per_share": 150.0,
            "acquired_disposed": "A",
            "classification": "Buy"
        }
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
            
    # Verify both signals were generated and stored in db
    stmt = select(DBSignal)
    result = await db_session.execute(stmt)
    signals = result.scalars().all()
    
    assert len(signals) >= 2
    types = [s.signal_type for s in signals]
    assert "insider_buying" in types
    assert "earnings_surprise" in types
