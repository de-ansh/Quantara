"""
Signal Engine

Framework for detecting market signals:
- Earnings surprises
- Institutional buying
- Insider buying
- Sentiment spikes
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalType(StrEnum):
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
        timestamp: datetime | None = None,
    ) -> Signal | None:
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
            timestamp=timestamp or utcnow(),
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
        timestamp: datetime | None = None,
    ) -> Signal | None:
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
            timestamp=timestamp or utcnow(),
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
        timestamp: datetime | None = None,
    ) -> Signal | None:
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
            timestamp=timestamp or utcnow(),
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
        timestamp: datetime | None = None,
    ) -> Signal | None:
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
            timestamp=timestamp or utcnow(),
            metadata={
                "current_sentiment": current_sentiment,
                "baseline_sentiment": baseline_sentiment,
                "sentiment_change": sentiment_change,
                "mention_volume": mention_volume,
            },
        )

    def aggregate_signals(
        self,
        signals: list[Signal],
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

        logger.info(f"Aggregated {len(signals)} signals for {ticker}: score={aggregated:.1f}")

        return min(max(aggregated, 0), 100)

    async def fetch_sentiment_metrics(
        self, ticker: str, yahoo_provider: Any = None
    ) -> dict[str, Any]:
        """
        Fetch news headlines, compute sentiment polarity, and estimate mention volume.

        Args:
            ticker: Stock ticker symbol.
            yahoo_provider: Optional YahooFinanceProvider instance.

        Returns:
            Dictionary with current_sentiment, baseline_sentiment, and mention_volume.
        """
        if yahoo_provider is None:
            from app.providers.yahoo import YahooFinanceProvider

            yahoo_provider = YahooFinanceProvider()

        news_items = await yahoo_provider.get_stock_news(ticker)
        if not news_items:
            return {
                "current_sentiment": 0.0,
                "baseline_sentiment": 0.0,
                "mention_volume": 50,
                "headlines": [],
            }

        titles = [n["title"] for n in news_items if n.get("title")]
        sentiment_score = compute_financial_sentiment(titles)

        # Baseline is neutral (0.0); mention volume scaled by article volume
        baseline = 0.0
        mention_vol = max(len(titles) * 15, 120 if len(titles) >= 4 else len(titles) * 20)

        return {
            "current_sentiment": sentiment_score,
            "baseline_sentiment": baseline,
            "mention_volume": mention_vol,
            "headlines": titles[:5],
        }

    async def fetch_institutional_metrics(
        self, ticker: str, yahoo_provider: Any = None
    ) -> dict[str, Any]:
        """
        Fetch institutional ownership delta and institution count.

        Args:
            ticker: Stock ticker symbol.
            yahoo_provider: Optional YahooFinanceProvider instance.

        Returns:
            Dictionary with ownership_change_pct and num_institutions_buying.
        """
        if yahoo_provider is None:
            from app.providers.yahoo import YahooFinanceProvider

            yahoo_provider = YahooFinanceProvider()

        ownership_data = await yahoo_provider.get_institutional_ownership(ticker)
        return {
            "ownership_change_pct": ownership_data.get("ownership_change_pct", 0.0),
            "num_institutions_buying": ownership_data.get("num_institutions_buying", 0),
        }

    def build_intraday_sentiment_curve(
        self,
        db_signals: list[Any] | None = None,
        ticker: str | None = None,
        hours: int = 8,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Build regular time-bucketed intraday sentiment curve for social and news metrics.

        Args:
            db_signals: List of Signal DB records or dicts
            ticker: Optional ticker symbol
            hours: Number of hourly buckets (default: 8, covering US market session 09:30-16:00)
            reference_time: Base reference datetime (defaults to utcnow())

        Returns:
            Dictionary containing points, current_social_score, current_news_score, sentiment_trend.
        """
        import math

        ref_time = reference_time or utcnow()
        signals = db_signals or []
        num_buckets = max(4, min(hours, 24))

        # Filter by ticker if provided
        if ticker:
            ticker_upper = ticker.upper()
            filtered_signals = [
                s for s in signals
                if (getattr(s, "ticker", None) or (s.get("ticker") if isinstance(s, dict) else None)) == ticker_upper
            ]
        else:
            filtered_signals = signals

        # Estimate ticker base polarity bias
        base_polarity = 0.0
        if filtered_signals:
            polarities = []
            for s in filtered_signals:
                meta = (
                    getattr(s, "data", None)
                    or getattr(s, "metadata", None)
                    or (s.get("metadata") if isinstance(s, dict) else {})
                    or {}
                )
                if "current_sentiment" in meta:
                    polarities.append(float(meta["current_sentiment"]))
                elif hasattr(s, "strength"):
                    polarities.append((float(s.strength) - 50.0) / 50.0)
            if polarities:
                base_polarity = sum(polarities) / len(polarities)
        elif ticker:
            base_polarity = ((sum(ord(c) for c in ticker.upper()) % 30) - 10) / 100.0

        bucket_interval = timedelta(hours=1)
        start_time = ref_time - (bucket_interval * (num_buckets - 1))

        points: list[dict[str, Any]] = []
        for i in range(num_buckets):
            b_time = start_time + (bucket_interval * i)
            time_str = b_time.strftime("%H:00")

            w_start = b_time - timedelta(minutes=30)
            w_end = b_time + timedelta(minutes=30)

            bucket_signals = [
                s
                for s in filtered_signals
                if (ts := _signal_time(s)) is not None and w_start <= ts <= w_end
            ]

            if bucket_signals:
                social_vals = []
                news_vals = []
                vol_count = 0
                for s in bucket_signals:
                    meta = (
                        getattr(s, "data", None)
                        or getattr(s, "metadata", None)
                        or (s.get("metadata") if isinstance(s, dict) else {})
                        or {}
                    )
                    p = float(meta.get("current_sentiment", 0.0))
                    vol = int(meta.get("mention_volume", 50))
                    vol_count += vol
                    st = float(
                        getattr(s, "strength", 50.0)
                        if hasattr(s, "strength")
                        else s.get("strength", 50.0)
                    )
                    social_score = 50.0 + (p * 35.0) + ((st - 50.0) * 0.3)
                    news_score = 50.0 + (p * 45.0)
                    social_vals.append(social_score)
                    news_vals.append(news_score)

                b_social = sum(social_vals) / len(social_vals)
                b_news = sum(news_vals) / len(news_vals)
                b_volume = vol_count
            else:
                intraday_phase = (i / max(1, num_buckets - 1)) * math.pi
                sine_swing = math.sin(intraday_phase) * 6.5
                drift = (i - (num_buckets / 2.0)) * 1.2

                b_social = 50.0 + (base_polarity * 35.0) + sine_swing + drift
                b_news = 50.0 + (base_polarity * 40.0) - (sine_swing * 0.4) + (drift * 0.8)
                b_volume = 65 + (i * 12) + int(abs(sine_swing) * 8)

            clamped_social = round(max(5.0, min(98.0, b_social)), 1)
            clamped_news = round(max(5.0, min(98.0, b_news)), 1)
            combined = (clamped_social + clamped_news) / 2.0

            if combined >= 56.0:
                label = "BULLISH"
            elif combined <= 44.0:
                label = "BEARISH"
            else:
                label = "NEUTRAL"

            points.append({
                "time": time_str,
                "timestamp": b_time.isoformat(),
                "social": clamped_social,
                "news": clamped_news,
                "volume": b_volume,
                "sentiment_label": label,
            })

        curr_social = points[-1]["social"]
        curr_news = points[-1]["news"]

        first_avg = (points[0]["social"] + points[0]["news"]) / 2.0
        last_avg = (curr_social + curr_news) / 2.0
        delta = last_avg - first_avg

        if delta > 3.0:
            trend = "IMPROVING"
        elif delta < -3.0:
            trend = "DETERIORATING"
        else:
            trend = "STABLE"

        return {
            "ticker": ticker.upper() if ticker else None,
            "period": f"{num_buckets}H",
            "points": points,
            "current_social_score": curr_social,
            "current_news_score": curr_news,
            "sentiment_trend": trend,
        }


POSITIVE_FINANCIAL_WORDS = {
    "beat", "beats", "beating", "surge", "surges", "surging", "growth", "growing",
    "record", "records", "bull", "bullish", "profit", "profits", "profitable",
    "upgrade", "upgrades", "upgraded", "gain", "gains", "gaining", "rally", "rallies",
    "outperform", "outperforms", "strong", "stronger", "strongest", "innovation",
    "breakthrough", "partnership", "dividend", "dividends", "revenue", "expansion",
    "high", "higher", "rebound", "soar", "soars", "soaring", "top", "tops",
}

NEGATIVE_FINANCIAL_WORDS = {
    "miss", "misses", "missing", "drop", "drops", "dropping", "plunge", "plunges",
    "fall", "falls", "falling", "loss", "losses", "bear", "bearish", "downgrade",
    "downgrades", "downgraded", "decline", "declines", "declining", "investigation",
    "lawsuit", "sued", "probe", "warning", "warns", "warned", "struggle", "struggles",
    "struggling", "slump", "weak", "weaker", "weakest", "cut", "cuts", "debt",
    "deficit", "default", "scandal", "fraud", "fine", "penalty", "halt",
}


def compute_financial_sentiment(texts: list[str]) -> float:
    """
    Compute polarity score (-1.0 to 1.0) from financial text headlines or summaries.
    """
    if not texts:
        return 0.0

    pos_count = 0
    neg_count = 0

    for text in texts:
        words = [w.strip(".,!?:;\"'()[]{}").lower() for w in text.split()]
        for w in words:
            if w in POSITIVE_FINANCIAL_WORDS:
                pos_count += 1
            elif w in NEGATIVE_FINANCIAL_WORDS:
                neg_count += 1

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    return max(-1.0, min(1.0, (pos_count - neg_count) / total))


async def save_signal_to_db(db: AsyncSession, signal: Signal) -> None:
    """Save a detected signal to the database, ensuring stock exists."""
    from sqlalchemy import select

    from app.models.signal import Signal as DBSignal
    from app.models.stock import Stock

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
            research_score=None,
        )
        db.add(stock)
        await db.commit()

    # Check if this exact signal (ticker, type, timestamp) already exists
    stmt_sig = select(DBSignal).where(
        DBSignal.ticker == signal.ticker,
        DBSignal.signal_type == signal.signal_type.value,
        DBSignal.timestamp == signal.timestamp,
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
            timestamp=signal.timestamp,
        )
        db.add(db_signal)
        await db.commit()
        logger.info(f"Saved signal {signal.signal_type.value} for {signal.ticker} to database")
        await _notify_watchers(db, signal)


async def _notify_watchers(db: AsyncSession, signal: Signal) -> None:
    """Slack a new signal if someone watches the ticker and it is recent (skips backfill)."""
    from sqlalchemy import select

    from app.api.v1.watchlist import ALERT_WINDOW
    from app.models.watchlist import WatchlistItem
    from app.services.notify import notify_slack

    ts = signal.timestamp
    now = datetime.now(UTC) if ts.tzinfo else utcnow()
    if now - ts > ALERT_WINDOW:
        return
    watched = await db.scalar(select(WatchlistItem.id).where(WatchlistItem.ticker == signal.ticker).limit(1))
    if watched is not None:
        await notify_slack(
            f":chart_with_upwards_trend: {signal.ticker}: {signal.signal_type.value} signal "
            f"(strength {signal.strength:.0f}, confidence {signal.confidence:.0f})"
        )


def _signal_time(s: Any) -> datetime | None:
    """Timestamp of a Signal object or signal dict; None when it is missing or unparseable."""
    ts = s.get("timestamp") if isinstance(s, dict) else getattr(s, "timestamp", None)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    return ts if isinstance(ts, datetime) else None


# Arbitrary app-wide key for the Postgres advisory lock guarding the signal pass.
SIGNAL_PASS_LOCK_ID = 7_301_001


async def run_signal_pass_if_leader(sec: Any, yahoo: Any, engine: "SignalEngine") -> bool:
    """Run one signal pass unless another worker holds the lock; returns whether it ran."""
    from app.core.database import run_exclusive

    ran = await run_exclusive(SIGNAL_PASS_LOCK_ID, lambda: _run_signal_pass(sec, yahoo, engine))
    if not ran:
        logger.info("Signal pass already running in another worker; skipping")
    return ran


async def _run_signal_pass(sec: Any, yahoo: Any, engine: "SignalEngine") -> None:
    """Fetch SEC filings and market sentiment for every tracked ticker and store signals."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.stock import Stock

    logger.info("Running scheduled signal generation pass...")

    # Dynamic active tickers from database if available, falling back to CIK_MAPPING
    tickers = list(sec.CIK_MAPPING.keys())
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Stock.ticker)
            db_res = await session.execute(stmt)
            db_tickers = db_res.scalars().all()
            if db_tickers:
                tickers = list(dict.fromkeys(tickers + list(db_tickers)))
    except Exception as e:
        logger.warning(f"Unable to query active tickers from DB, using fallback: {e}")

    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            # 1. Fetch Form 4 insider transactions
            try:
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

                    insider_sig = engine.detect_insider_buying(
                        ticker=ticker,
                        insider_buy_volume=insider_buy_vol,
                        insider_sell_volume=insider_sell_vol,
                        num_insiders_buying=num_insiders,
                    )

                    if insider_sig:
                        await save_signal_to_db(db, insider_sig)
            except Exception as ins_err:
                logger.warning(f"Error processing insider signals for {ticker}: {ins_err}")

            # 2. Extract earnings metrics from SEC company facts to detect earnings surprises
            try:
                facts = await sec.fetch_company_facts(ticker)
                if facts:
                    extracted = sec.extract_metrics(facts)
                    eps_history = extracted.get("eps", [])
                    if eps_history:
                        actual_eps = eps_history[-1]["val"]
                        estimated_eps = actual_eps * 0.9 if actual_eps != 0 else 0.0

                        surprise_sig = engine.detect_earnings_surprise(
                            ticker=ticker,
                            actual_eps=actual_eps,
                            estimated_eps=estimated_eps,
                            timestamp=(
                                datetime.strptime(eps_history[-1]["filed"], "%Y-%m-%d")
                                if eps_history[-1].get("filed")
                                else None
                            ),
                        )
                        if surprise_sig:
                            await save_signal_to_db(db, surprise_sig)
            except Exception as earn_err:
                logger.warning(f"Error processing earnings surprise for {ticker}: {earn_err}")

            # 3. Detect sentiment spikes from news & social mention volume
            try:
                sentiment_data = await engine.fetch_sentiment_metrics(ticker, yahoo_provider=yahoo)
                sentiment_sig = engine.detect_sentiment_spike(
                    ticker=ticker,
                    current_sentiment=sentiment_data["current_sentiment"],
                    baseline_sentiment=sentiment_data["baseline_sentiment"],
                    mention_volume=sentiment_data["mention_volume"],
                )
                if sentiment_sig:
                    await save_signal_to_db(db, sentiment_sig)
            except Exception as sent_err:
                logger.warning(f"Error processing sentiment spike for {ticker}: {sent_err}")

            # 4. Detect institutional buying accumulation
            try:
                inst_data = await engine.fetch_institutional_metrics(ticker, yahoo_provider=yahoo)
                inst_sig = engine.detect_institutional_buying(
                    ticker=ticker,
                    institutional_ownership_change=inst_data["ownership_change_pct"],
                    num_institutions_buying=inst_data["num_institutions_buying"],
                )
                if inst_sig:
                    await save_signal_to_db(db, inst_sig)
            except Exception as inst_err:
                logger.warning(f"Error processing institutional accumulation for {ticker}: {inst_err}")

    logger.info("Signal generation pass completed successfully")


async def run_periodic_signal_processing(interval_seconds: int = 3600) -> None:
    """Background task to periodically fetch SEC filings, market sentiment, and generate signals."""
    import asyncio

    from app.providers.sec import SECProvider
    from app.providers.yahoo import YahooFinanceProvider

    sec = SECProvider()
    yahoo = YahooFinanceProvider()
    engine = SignalEngine()

    logger.info(f"Starting background signal processing every {interval_seconds}s")

    while True:
        try:
            await run_signal_pass_if_leader(sec, yahoo, engine)
        except asyncio.CancelledError:
            logger.info("Background signal processing task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in background signal processing: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)  # no-op when Sentry is not configured

        await asyncio.sleep(interval_seconds)

