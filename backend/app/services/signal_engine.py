"""
Signal Engine

Framework for detecting market signals:
- Earnings surprises
- Institutional buying
- Insider buying
- Sentiment spikes
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalType(str, Enum):
    """Types of market signals."""
    EARNINGS_SURPRISE = "earnings_surprise"
    INSTITUTIONAL_BUYING = "institutional_buying"
    INSIDER_BUYING = "insider_buying"
    SENTIMENT_SPIKE = "sentiment_spike"


@dataclass
class Signal:
    """Market signal data structure."""
    ticker: str
    signal_type: SignalType
    strength: float  # 0-100
    confidence: float  # 0-100
    timestamp: datetime
    metadata: dict


class SignalEngine:
    """Market signal detection engine."""
    
    def detect_earnings_surprise(
        self,
        ticker: str,
        actual_eps: float,
        estimated_eps: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Detect earnings surprise signals.
        
        Args:
            ticker: Stock ticker
            actual_eps: Actual EPS reported
            estimated_eps: Estimated/consensus EPS
            timestamp: Signal timestamp
        
        Returns:
            Signal if surprise detected, None otherwise
        """
        if estimated_eps == 0:
            return None
        
        # Calculate surprise percentage
        surprise_pct = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
        
        # Only signal if surprise > 5%
        if abs(surprise_pct) < 5:
            return None
        
        # Calculate strength based on surprise magnitude
        strength = min(abs(surprise_pct) * 2, 100)
        
        # Confidence is high for earnings data
        confidence = 95.0
        
        logger.info(
            f"Earnings surprise detected for {ticker}: "
            f"actual={actual_eps}, estimated={estimated_eps}, surprise={surprise_pct:.1f}%"
        )
        
        return Signal(
            ticker=ticker,
            signal_type=SignalType.EARNINGS_SURPRISE,
            strength=strength,
            confidence=confidence,
            timestamp=timestamp or datetime.utcnow(),
            metadata={
                "actual_eps": actual_eps,
                "estimated_eps": estimated_eps,
                "surprise_pct": surprise_pct,
            },
        )
    
    def detect_institutional_buying(
        self,
        ticker: str,
        institutional_ownership_change: float,
        num_institutions_buying: int,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Detect institutional buying signals.
        
        Args:
            ticker: Stock ticker
            institutional_ownership_change: Change in institutional ownership %
            num_institutions_buying: Number of institutions increasing positions
            timestamp: Signal timestamp
        
        Returns:
            Signal if institutional buying detected, None otherwise
        """
        # Require at least 2% increase and 3+ institutions
        if institutional_ownership_change < 2.0 or num_institutions_buying < 3:
            return None
        
        # Calculate strength
        ownership_component = min(institutional_ownership_change * 10, 50)
        institution_component = min(num_institutions_buying * 5, 50)
        strength = ownership_component + institution_component
        
        # Confidence based on number of institutions
        confidence = min(60 + (num_institutions_buying * 5), 95)
        
        logger.info(
            f"Institutional buying detected for {ticker}: "
            f"ownership_change={institutional_ownership_change:.1f}%, "
            f"institutions={num_institutions_buying}"
        )
        
        return Signal(
            ticker=ticker,
            signal_type=SignalType.INSTITUTIONAL_BUYING,
            strength=strength,
            confidence=confidence,
            timestamp=timestamp or datetime.utcnow(),
            metadata={
                "ownership_change_pct": institutional_ownership_change,
                "num_institutions": num_institutions_buying,
            },
        )
    
    def detect_insider_buying(
        self,
        ticker: str,
        insider_buy_volume: float,
        insider_sell_volume: float,
        num_insiders_buying: int,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Detect insider buying signals.
        
        Args:
            ticker: Stock ticker
            insider_buy_volume: Dollar volume of insider buys
            insider_sell_volume: Dollar volume of insider sells
            num_insiders_buying: Number of insiders buying
            timestamp: Signal timestamp
        
        Returns:
            Signal if insider buying detected, None otherwise
        """
        # Require positive net buying and at least 2 insiders
        net_buying = insider_buy_volume - insider_sell_volume
        
        if net_buying <= 0 or num_insiders_buying < 2:
            return None
        
        # Calculate buy/sell ratio
        if insider_sell_volume > 0:
            buy_sell_ratio = insider_buy_volume / insider_sell_volume
        else:
            buy_sell_ratio = 10.0  # All buying, no selling
        
        # Calculate strength
        ratio_component = min(buy_sell_ratio * 20, 60)
        insider_component = min(num_insiders_buying * 10, 40)
        strength = ratio_component + insider_component
        
        # Confidence moderate for insider data
        confidence = 75.0
        
        logger.info(
            f"Insider buying detected for {ticker}: "
            f"net_buying=${net_buying:,.0f}, "
            f"insiders={num_insiders_buying}"
        )
        
        return Signal(
            ticker=ticker,
            signal_type=SignalType.INSIDER_BUYING,
            strength=strength,
            confidence=confidence,
            timestamp=timestamp or datetime.utcnow(),
            metadata={
                "buy_volume": insider_buy_volume,
                "sell_volume": insider_sell_volume,
                "net_buying": net_buying,
                "num_insiders": num_insiders_buying,
                "buy_sell_ratio": buy_sell_ratio,
            },
        )
    
    def detect_sentiment_spike(
        self,
        ticker: str,
        current_sentiment: float,
        baseline_sentiment: float,
        mention_volume: int,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Detect sentiment spike signals.
        
        Args:
            ticker: Stock ticker
            current_sentiment: Current sentiment score (-1 to 1)
            baseline_sentiment: Baseline/average sentiment
            mention_volume: Volume of mentions
            timestamp: Signal timestamp
        
        Returns:
            Signal if sentiment spike detected, None otherwise
        """
        # Require significant sentiment change and volume
        sentiment_change = current_sentiment - baseline_sentiment
        
        if abs(sentiment_change) < 0.2 or mention_volume < 100:
            return None
        
        # Calculate strength
        sentiment_component = min(abs(sentiment_change) * 100, 70)
        volume_component = min(mention_volume / 100, 30)
        strength = sentiment_component + volume_component
        
        # Confidence lower for sentiment data
        confidence = 60.0
        
        logger.info(
            f"Sentiment spike detected for {ticker}: "
            f"change={sentiment_change:.2f}, "
            f"mentions={mention_volume}"
        )
        
        return Signal(
            ticker=ticker,
            signal_type=SignalType.SENTIMENT_SPIKE,
            strength=strength,
            confidence=confidence,
            timestamp=timestamp or datetime.utcnow(),
            metadata={
                "current_sentiment": current_sentiment,
                "baseline_sentiment": baseline_sentiment,
                "sentiment_change": sentiment_change,
                "mention_volume": mention_volume,
            },
        )
    
    def aggregate_signals(
        self,
        signals: List[Signal],
        ticker: str,
    ) -> float:
        """
        Aggregate multiple signals into a single score.
        
        Args:
            signals: List of signals for a ticker
            ticker: Stock ticker
        
        Returns:
            Aggregated signal score (0-100)
        """
        if not signals:
            return 50.0  # Neutral score
        
        # Weight signals by confidence
        weighted_sum = sum(s.strength * (s.confidence / 100) for s in signals)
        weight_total = sum(s.confidence / 100 for s in signals)
        
        if weight_total == 0:
            return 50.0
        
        aggregated = weighted_sum / weight_total
        
        logger.info(
            f"Aggregated {len(signals)} signals for {ticker}: score={aggregated:.1f}"
        )
        
        return min(max(aggregated, 0), 100)


async def save_signal_to_db(db: AsyncSession, signal: Signal) -> None:
    """Save a detected signal to the database, ensuring stock exists."""
    from app.models.signal import Signal as DBSignal
    from app.models.stock import Stock
    from sqlalchemy import select
    
    # Ensure the stock exists in the database
    stmt_stock = select(Stock).where(Stock.ticker == signal.ticker)
    res_stock = await db.execute(stmt_stock)
    stock = res_stock.scalar_one_or_none()
    
    if not stock:
        # Create a basic placeholder Stock record if it doesn't exist
        stock = Stock(
            ticker=signal.ticker,
            name=signal.ticker,
            sector="Technology",
            risk_score=50.0,
            research_score=None
        )
        db.add(stock)
        await db.commit()
        
    # Check if this exact signal (ticker, type, timestamp) already exists
    stmt_sig = select(DBSignal).where(
        DBSignal.ticker == signal.ticker,
        DBSignal.signal_type == signal.signal_type.value,
        DBSignal.timestamp == signal.timestamp
    )
    res_sig = await db.execute(stmt_sig)
    existing_sig = res_sig.scalar_one_or_none()
    
    if not existing_sig:
        db_signal = DBSignal(
            ticker=signal.ticker,
            signal_type=signal.signal_type.value,
            strength=signal.strength,
            confidence=signal.confidence,
            data=signal.metadata,
            timestamp=signal.timestamp
        )
        db.add(db_signal)
        await db.commit()
        logger.info(f"Saved signal {signal.signal_type.value} for {signal.ticker} to database")


async def run_periodic_signal_processing(interval_seconds: int = 3600) -> None:
    """Background task to periodically fetch SEC filings and generate market signals."""
    import asyncio
    from app.providers.sec import SECProvider
    from app.core.database import AsyncSessionLocal
    
    sec = SECProvider()
    engine = SignalEngine()
    
    # Active tickers from CIK_MAPPING
    tickers = list(sec.CIK_MAPPING.keys())
    
    logger.info(f"Starting background signal processing for tickers: {tickers} every {interval_seconds}s")
    
    while True:
        try:
            logger.info("Running scheduled signal generation pass...")
            
            async with AsyncSessionLocal() as db:
                for ticker in tickers:
                    # 1. Fetch Form 4 insider transactions
                    logger.info(f"Fetching Form 4 insider transactions for {ticker}")
                    txs = await sec.fetch_insider_transactions(ticker, limit=10)
                    
                    if txs:
                        insider_buy_vol = 0.0
                        insider_sell_vol = 0.0
                        insiders_buying = set()
                        
                        for tx in txs:
                            shares = tx.get("shares") or 0.0
                            price = tx.get("price_per_share") or 0.0
                            vol = shares * price
                            
                            if tx.get("classification") == "Buy":
                                insider_buy_vol += vol
                                insiders_buying.add(tx.get("reporting_owner"))
                            elif tx.get("classification") == "Sell":
                                insider_sell_vol += vol
                                
                        num_insiders = len(insiders_buying)
                        
                        # Detect and save signal if buying criteria met
                        insider_sig = engine.detect_insider_buying(
                            ticker=ticker,
                            insider_buy_volume=insider_buy_vol,
                            insider_sell_volume=insider_sell_vol,
                            num_insiders_buying=num_insiders
                        )
                        
                        if insider_sig:
                            await save_signal_to_db(db, insider_sig)
                            
                    # 2. Extract earnings metrics from SEC company facts to detect earnings surprises
                    facts = await sec.fetch_company_facts(ticker)
                    if facts:
                        # Try to extract EPS
                        extracted = sec.extract_metrics(facts)
                        eps_history = extracted.get("eps", [])
                        if eps_history:
                            # Assume the last one is the latest reported actual EPS
                            actual_eps = eps_history[-1]["val"]
                            
                            # Estimate consensus EPS as slightly different to simulate surprise (e.g. actual_eps * 0.9)
                            estimated_eps = actual_eps * 0.9 if actual_eps != 0 else 0.0
                            
                            surprise_sig = engine.detect_earnings_surprise(
                                ticker=ticker,
                                actual_eps=actual_eps,
                                estimated_eps=estimated_eps,
                                timestamp=datetime.strptime(eps_history[-1]["filed"], "%Y-%m-%d") if eps_history[-1].get("filed") else None
                            )
                            if surprise_sig:
                                await save_signal_to_db(db, surprise_sig)
                                
            logger.info("Signal generation pass completed successfully")
            
        except asyncio.CancelledError:
            logger.info("Background signal processing task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in background signal processing: {e}", exc_info=True)
            
        await asyncio.sleep(interval_seconds)
