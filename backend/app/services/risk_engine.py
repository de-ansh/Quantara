"""
Deterministic Risk Engine - Pure Python Implementation

This module implements a comprehensive risk scoring algorithm that is:
- Deterministic (no LLM dependencies)
- Independently testable
- Transparent and auditable

Risk Score Formula:
    (0.2 * volatility_score) +
    (0.15 * beta_score) +
    (0.2 * leverage_score) +
    (0.15 * earnings_stability_score) +
    (0.1 * sector_risk_score) +
    (0.2 * valuation_risk_score)

All scores normalized to 0-100 scale.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class RiskLevel(StrEnum):
    """Risk level classifications."""

    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


@dataclass
class RiskComponents:
    """Individual risk component scores."""

    volatility_score: float
    beta_score: float
    leverage_score: float
    earnings_stability_score: float
    sector_risk_score: float
    valuation_risk_score: float


@dataclass
class RiskAnalysis:
    """Complete risk analysis result."""

    ticker: str
    overall_risk_score: float
    risk_level: RiskLevel
    components: RiskComponents
    risk_band: str
    explanation: str


class RiskEngine:
    """Deterministic risk scoring engine."""

    # Component weights
    WEIGHTS = {
        "volatility": 0.20,
        "beta": 0.15,
        "leverage": 0.20,
        "earnings_stability": 0.15,
        "sector": 0.10,
        "valuation": 0.20,
    }

    # Risk level thresholds
    CONSERVATIVE_THRESHOLD = 33.33
    MODERATE_THRESHOLD = 66.67

    # Sector risk mappings (example - should be data-driven)
    SECTOR_RISK_MAP = {
        "Technology": 65,
        "Healthcare": 55,
        "Financials": 60,
        "Energy": 70,
        "Utilities": 30,
        "Consumer Staples": 35,
        "Consumer Discretionary": 55,
        "Industrials": 50,
        "Materials": 60,
        "Real Estate": 50,
        "Communication Services": 55,
    }

    def calculate_volatility_score(
        self, historical_volatility: float, volatility_percentile: float | None = None
    ) -> float:
        """
        Calculate volatility risk score.

        Args:
            historical_volatility: Annualized volatility (e.g., 0.25 for 25%)
            volatility_percentile: Percentile rank vs market (0-100)

        Returns:
            Volatility score (0-100, higher = riskier)
        """
        # Convert volatility to percentage
        vol_pct = historical_volatility * 100

        # Normalize: 0% vol = 0 score, 100% vol = 100 score
        # Most stocks fall in 10-50% range
        base_score = min(vol_pct * 2, 100)

        # Adjust by percentile if available
        if volatility_percentile is not None:
            base_score = (base_score * 0.6) + (volatility_percentile * 0.4)

        return min(max(base_score, 0), 100)

    def calculate_beta_score(self, beta: float) -> float:
        """
        Calculate beta risk score.

        Args:
            beta: Stock beta vs market (e.g., 1.5)

        Returns:
            Beta score (0-100, higher = riskier)
        """
        # Beta of 1.0 = market risk (50 score)
        # Beta of 0.0 = no risk (0 score)
        # Beta of 2.0+ = very high risk (100 score)

        if beta < 0:
            # Negative beta is actually lower risk (inverse correlation)
            return max(0, 50 + (beta * 25))

        # Normalize: beta 0-2 maps to score 0-100
        score = beta * 50
        return min(max(score, 0), 100)

    def calculate_leverage_score(
        self, debt_to_equity: float, interest_coverage: float | None = None
    ) -> float:
        """
        Calculate leverage risk score.

        Args:
            debt_to_equity: Debt-to-equity ratio
            interest_coverage: Interest coverage ratio (EBIT/Interest)

        Returns:
            Leverage score (0-100, higher = riskier)
        """
        # D/E ratio scoring
        # 0.0 = 0 score, 1.0 = 50 score, 3.0+ = 100 score
        de_score = min((debt_to_equity / 3.0) * 100, 100)

        # Interest coverage adjustment
        if interest_coverage is not None:
            if interest_coverage < 1.5:
                # Very risky - can't cover interest
                coverage_penalty = 30
            elif interest_coverage < 3.0:
                coverage_penalty = 15
            elif interest_coverage < 5.0:
                coverage_penalty = 5
            else:
                coverage_penalty = 0

            de_score = min(de_score + coverage_penalty, 100)

        return min(max(de_score, 0), 100)

    def calculate_earnings_stability_score(
        self, earnings_volatility: float, consecutive_profitable_quarters: int
    ) -> float:
        """
        Calculate earnings stability risk score.

        Args:
            earnings_volatility: Standard deviation of quarterly earnings
            consecutive_profitable_quarters: Number of consecutive profitable quarters

        Returns:
            Earnings stability score (0-100, higher = riskier)
        """
        # High volatility = high risk
        volatility_score = min(earnings_volatility * 100, 100)

        # More consecutive profitable quarters = lower risk
        if consecutive_profitable_quarters >= 12:
            stability_bonus = -30
        elif consecutive_profitable_quarters >= 8:
            stability_bonus = -20
        elif consecutive_profitable_quarters >= 4:
            stability_bonus = -10
        else:
            stability_bonus = 20  # Penalty for inconsistent profitability

        final_score = volatility_score + stability_bonus
        return min(max(final_score, 0), 100)

    def calculate_sector_risk_score(self, sector: str) -> float:
        """
        Calculate sector-based risk score.

        Args:
            sector: Sector name

        Returns:
            Sector risk score (0-100, higher = riskier)
        """
        return self.SECTOR_RISK_MAP.get(sector, 50)  # Default to moderate risk

    def calculate_valuation_risk_score(
        self,
        pe_ratio: float | None = None,
        price_to_book: float | None = None,
        price_to_sales: float | None = None,
    ) -> float:
        """
        Calculate valuation risk score.

        Args:
            pe_ratio: Price-to-earnings ratio
            price_to_book: Price-to-book ratio
            price_to_sales: Price-to-sales ratio

        Returns:
            Valuation risk score (0-100, higher = riskier)
        """
        scores = []

        if pe_ratio is not None and pe_ratio > 0:
            # P/E scoring: 0-15 = low risk, 15-30 = moderate, 30+ = high
            pe_score = min((pe_ratio / 50) * 100, 100)
            scores.append(pe_score)

        if price_to_book is not None and price_to_book > 0:
            # P/B scoring: 0-2 = low risk, 2-5 = moderate, 5+ = high
            pb_score = min((price_to_book / 8) * 100, 100)
            scores.append(pb_score)

        if price_to_sales is not None and price_to_sales > 0:
            # P/S scoring: 0-2 = low risk, 2-5 = moderate, 5+ = high
            ps_score = min((price_to_sales / 8) * 100, 100)
            scores.append(ps_score)

        # Average available valuation metrics
        if scores:
            return sum(scores) / len(scores)

        return 50  # Default to moderate risk if no data

    def calculate_overall_risk(self, components: RiskComponents) -> float:
        """
        Calculate overall risk score from components.

        Args:
            components: Individual risk component scores

        Returns:
            Overall risk score (0-100)
        """
        overall = (
            self.WEIGHTS["volatility"] * components.volatility_score
            + self.WEIGHTS["beta"] * components.beta_score
            + self.WEIGHTS["leverage"] * components.leverage_score
            + self.WEIGHTS["earnings_stability"] * components.earnings_stability_score
            + self.WEIGHTS["sector"] * components.sector_risk_score
            + self.WEIGHTS["valuation"] * components.valuation_risk_score
        )

        return min(max(overall, 0), 100)

    def classify_risk_level(self, risk_score: float) -> RiskLevel:
        """
        Classify risk score into risk level.

        Args:
            risk_score: Overall risk score (0-100)

        Returns:
            Risk level classification
        """
        if risk_score <= self.CONSERVATIVE_THRESHOLD:
            return RiskLevel.CONSERVATIVE
        elif risk_score <= self.MODERATE_THRESHOLD:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.AGGRESSIVE

    def get_risk_band(self, risk_score: float) -> str:
        """
        Get risk band description.

        Args:
            risk_score: Overall risk score (0-100)

        Returns:
            Risk band string (e.g., "0-33")
        """
        if risk_score <= self.CONSERVATIVE_THRESHOLD:
            return "0-33"
        elif risk_score <= self.MODERATE_THRESHOLD:
            return "34-66"
        else:
            return "67-100"

    def generate_explanation(
        self, ticker: str, risk_score: float, risk_level: RiskLevel, components: RiskComponents
    ) -> str:
        """
        Generate human-readable risk explanation.

        Args:
            ticker: Stock ticker
            risk_score: Overall risk score
            risk_level: Risk level classification
            components: Risk components

        Returns:
            Explanation text
        """
        # Find highest risk components
        component_scores = {
            "Volatility": components.volatility_score,
            "Beta": components.beta_score,
            "Leverage": components.leverage_score,
            "Earnings Stability": components.earnings_stability_score,
            "Sector": components.sector_risk_score,
            "Valuation": components.valuation_risk_score,
        }

        sorted_components = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)

        top_risks = sorted_components[:2]

        explanation = (
            f"{ticker} has an overall risk score of {risk_score:.1f}, "
            f"classified as {risk_level.value}. "
            f"Primary risk factors are {top_risks[0][0]} ({top_risks[0][1]:.1f}) "
            f"and {top_risks[1][0]} ({top_risks[1][1]:.1f})."
        )

        return explanation

    def analyze_stock_risk(
        self,
        ticker: str,
        historical_volatility: float,
        beta: float,
        debt_to_equity: float,
        earnings_volatility: float,
        consecutive_profitable_quarters: int,
        sector: str,
        volatility_percentile: float | None = None,
        interest_coverage: float | None = None,
        pe_ratio: float | None = None,
        price_to_book: float | None = None,
        price_to_sales: float | None = None,
    ) -> RiskAnalysis:
        """
        Perform complete risk analysis on a stock.

        Args:
            ticker: Stock ticker symbol
            historical_volatility: Annualized volatility
            beta: Stock beta vs market
            debt_to_equity: Debt-to-equity ratio
            earnings_volatility: Earnings volatility
            consecutive_profitable_quarters: Consecutive profitable quarters
            sector: Stock sector
            volatility_percentile: Optional volatility percentile
            interest_coverage: Optional interest coverage ratio
            pe_ratio: Optional P/E ratio
            price_to_book: Optional P/B ratio
            price_to_sales: Optional P/S ratio

        Returns:
            Complete risk analysis
        """
        logger.info(f"Analyzing risk for {ticker}")

        # Calculate individual components
        components = RiskComponents(
            volatility_score=self.calculate_volatility_score(
                historical_volatility, volatility_percentile
            ),
            beta_score=self.calculate_beta_score(beta),
            leverage_score=self.calculate_leverage_score(debt_to_equity, interest_coverage),
            earnings_stability_score=self.calculate_earnings_stability_score(
                earnings_volatility, consecutive_profitable_quarters
            ),
            sector_risk_score=self.calculate_sector_risk_score(sector),
            valuation_risk_score=self.calculate_valuation_risk_score(
                pe_ratio, price_to_book, price_to_sales
            ),
        )

        # Calculate overall risk
        overall_risk = self.calculate_overall_risk(components)
        risk_level = self.classify_risk_level(overall_risk)
        risk_band = self.get_risk_band(overall_risk)
        explanation = self.generate_explanation(ticker, overall_risk, risk_level, components)

        logger.info(
            f"Risk analysis complete for {ticker}: "
            f"score={overall_risk:.1f}, level={risk_level.value}"
        )

        return RiskAnalysis(
            ticker=ticker,
            overall_risk_score=overall_risk,
            risk_level=risk_level,
            components=components,
            risk_band=risk_band,
            explanation=explanation,
        )

    def generate_drawdown_series(
        self,
        df: Any | None = None,
        historical_volatility: float = 0.25,
        overall_risk_score: float = 50.0,
        max_drawdown: float | None = None,
    ) -> tuple[float, list[dict[str, Any]]]:
        """
        Generate historical underwater drawdown series and projected stress trajectory.

        Args:
            df: Historical price DataFrame (optional, from Yahoo Finance)
            historical_volatility: Annualized volatility (e.g., 0.25)
            overall_risk_score: Normalized risk score (0-100)
            max_drawdown: Precomputed max drawdown if available

        Returns:
            Tuple of (max_drawdown_value, list of drawdown data points)
        """
        points: list[dict[str, Any]] = []
        computed_max_dd: float = (
            max_drawdown if max_drawdown is not None and max_drawdown < 0 else -0.25
        )

        has_valid_df = (
            df is not None
            and hasattr(df, "empty")
            and not df.empty
            and hasattr(df, "columns")
        )

        if has_valid_df:
            assert df is not None  # narrowed by has_valid_df
            try:
                price_col = (
                    "Close"
                    if "Close" in df.columns
                    else ("Adj Close" if "Adj Close" in df.columns else df.columns[0])
                )
                prices = df[price_col].dropna()
                if len(prices) >= 5:
                    returns = prices.pct_change().fillna(0.0)
                    cumulative_returns = (1.0 + returns).cumprod()
                    peak = cumulative_returns.cummax()
                    drawdown = (cumulative_returns - peak) / peak
                    computed_max_dd = float(drawdown.min())

                    # Sample 12 evenly spaced points across historical period
                    total_len = len(drawdown)
                    if total_len <= 12:
                        indices = list(range(total_len))
                    else:
                        step = (total_len - 1) / 11.0
                        indices = sorted({int(round(i * step)) for i in range(12)})

                    for idx in indices:
                        ts = drawdown.index[idx]
                        if hasattr(ts, "strftime"):
                            time_str = ts.strftime("%b '%y")
                        else:
                            time_str = f"T-{total_len - idx}"

                        dd_val = float(drawdown.iloc[idx])
                        recovery_level = round(max(0.0, min(100.0, (1.0 + dd_val) * 100.0)), 1)
                        points.append(
                            {
                                "time": time_str,
                                "historical": recovery_level,
                                "projected": None,
                                "drawdown_pct": round(dd_val * 100.0, 1),
                            }
                        )
            except Exception as e:
                logger.warning(f"Error computing drawdown from DataFrame: {e}")
                points = []

        if not points:
            # Deterministic fallback drawdown curve
            depth = abs(computed_max_dd)
            sample_factors = [
                0.0,
                0.15,
                0.08,
                0.35,
                0.28,
                0.65,
                0.50,
                1.00,
                0.75,
                0.45,
                0.55,
                0.30,
            ]
            months = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]

            for i, factor in enumerate(sample_factors):
                dd_val = -factor * depth
                level = round(max(0.0, min(100.0, (1.0 + dd_val) * 100.0)), 1)
                points.append(
                    {
                        "time": f"{months[i % 12]} '24",
                        "historical": level,
                        "projected": None,
                        "drawdown_pct": round(dd_val * 100.0, 1),
                    }
                )

        # Connect projection seamlessly from the latest historical level
        last_level = points[-1]["historical"] or 100.0
        points[-1]["projected"] = last_level

        # Forward stress projection based on risk score and volatility
        shock = min(
            0.65,
            max(
                0.12,
                (overall_risk_score / 100.0) * max(0.2, historical_volatility) * 1.5,
            ),
        )
        proj_steps = [
            ("+1M (Shock)", round(max(5.0, min(100.0, last_level * (1.0 - 0.25 * shock))), 1)),
            ("+2M (Trough)", round(max(5.0, min(100.0, last_level * (1.0 - 0.65 * shock))), 1)),
            ("+3M (Stress)", round(max(5.0, min(100.0, last_level * (1.0 - 1.00 * shock))), 1)),
            ("+4M (Rebound)", round(max(5.0, min(100.0, last_level * (1.0 - 0.85 * shock))), 1)),
        ]

        for p_label, p_val in proj_steps:
            points.append(
                {
                    "time": p_label,
                    "historical": None,
                    "projected": p_val,
                    "drawdown_pct": round((p_val / 100.0 - 1.0) * 100.0, 1),
                }
            )

        return computed_max_dd, points

    def calculate_factor_sensitivities(
        self,
        ticker: str,
        beta: float = 1.0,
        pe_ratio: float | None = None,
        debt_to_equity: float | None = None,
        sector: str = "Technology",
    ) -> dict[str, float]:
        """
        Calculate quantitative macro factor sensitivities (betas) for an asset.

        Factors:
        - market_beta: Sensitivity to broad equity market (S&P 500)
        - interest_rate_beta: Sensitivity to interest rate moves (duration / multiple compression)
        - oil_beta: Sensitivity to energy/commodity input costs
        - tech_momentum_beta: Sensitivity to technology and AI innovation cycle
        - credit_spread_beta: Sensitivity to debt refinancing and credit widening
        """
        b = beta if beta is not None else 1.0
        pe = pe_ratio if pe_ratio and pe_ratio > 0 else 22.0
        de = debt_to_equity if debt_to_equity is not None and debt_to_equity >= 0 else 0.5
        sec = (sector or "Technology").lower()

        # 1. Market Beta
        market_beta = round(float(b), 2)

        # 2. Interest Rate / Duration Sensitivity
        pe_factor = min(3.0, max(0.5, pe / 18.0))
        leverage_multiplier = 1.0 + min(2.0, de * 0.5)
        rate_beta = round(-1.2 * pe_factor * leverage_multiplier, 2)

        # 3. Commodity / Oil Beta
        if "energy" in sec or "oil" in sec:
            oil_beta = 1.45
        elif "utilit" in sec:
            oil_beta = -0.35
        elif "transport" in sec or "airline" in sec or "consumer" in sec:
            oil_beta = -0.85
        elif "tech" in sec or "semiconductor" in sec:
            oil_beta = -0.25
        elif "financ" in sec:
            oil_beta = 0.15
        else:
            oil_beta = -0.30

        # 4. Tech / Growth Momentum Beta
        if "tech" in sec or "semiconductor" in sec or "software" in sec:
            tech_beta = round(1.35 * b, 2)
        elif "communicat" in sec:
            tech_beta = round(1.05 * b, 2)
        elif "health" in sec:
            tech_beta = 0.40
        elif "utilit" in sec or "reit" in sec:
            tech_beta = 0.15
        else:
            tech_beta = 0.50

        # 5. Credit Spread Beta (widening credit spread penalty)
        credit_beta = round(-0.8 * (1.0 + de * 1.5), 2)

        return {
            "market_beta": market_beta,
            "interest_rate_beta": rate_beta,
            "oil_beta": round(oil_beta, 2),
            "tech_momentum_beta": tech_beta,
            "credit_spread_beta": credit_beta,
        }

    def run_scenario_stress_test(
        self,
        ticker: str,
        beta: float = 1.0,
        pe_ratio: float | None = None,
        debt_to_equity: float | None = None,
        sector: str = "Technology",
    ) -> list[dict[str, Any]]:
        """
        Run multi-factor macroeconomic stress test scenarios based on factor sensitivities.

        Returns list of structured scenarios with projected % impact and factor attribution.
        """
        sens = self.calculate_factor_sensitivities(
            ticker=ticker,
            beta=beta,
            pe_ratio=pe_ratio,
            debt_to_equity=debt_to_equity,
            sector=sector,
        )

        is_indian = ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO") or ".NS" in ticker.upper()

        if is_indian:
            scenarios_definitions: list[dict[str, Any]] = [
                {
                    "id": "rbi_repo_rate_hike_50bps",
                    "name": "RBI Repo Rate Hike +50bps",
                    "type": "Monetary Policy Tightening",
                    "description": "Reserve Bank of India raises repo rate +50bps to curb inflation, elevating domestic borrowing costs.",
                    "shocks": {
                        "interest_rate_beta": 4.5,
                        "market_beta": -2.2,
                        "credit_spread_beta": 1.2,
                    },
                    "category": "macro_monetary",
                },
                {
                    "id": "crude_spike_100_inr_depreciation",
                    "name": "Brent Crude $100 + INR Depreciation",
                    "type": "Current Account Shock",
                    "description": "Crude oil import bill surge, current account deficit widening, and INR sliding past ₹86/USD.",
                    "shocks": {
                        "oil_beta": 12.0,
                        "market_beta": -5.0,
                        "interest_rate_beta": 1.8,
                    },
                    "category": "commodity_geopolitical",
                },
                {
                    "id": "india_capex_cycle_acceleration",
                    "name": "National Capex & PLI Acceleration",
                    "type": "Infrastructure Catalyst",
                    "description": "Government infrastructure outlay accelerates alongside PLI domestic manufacturing expansion.",
                    "shocks": {
                        "market_beta": 6.5,
                        "credit_spread_beta": -2.0,
                        "tech_momentum_beta": 4.0,
                    },
                    "category": "industry_catalyst",
                },
                {
                    "id": "monsoon_deficit_rural_slowdown",
                    "name": "Monsoon Deficit & Rural Slowdown",
                    "type": "Agrarian & FMCG Headwind",
                    "description": "Uneven southwest monsoon rainfall pressures rural disposable income and consumer goods volume.",
                    "shocks": {
                        "market_beta": -4.0,
                        "oil_beta": 3.0,
                        "credit_spread_beta": 2.5,
                    },
                    "category": "macro_economic",
                },
                {
                    "id": "global_tech_slowdown",
                    "name": "Global Tech Offshore Budget Cut",
                    "type": "Export Discretionary Drag",
                    "description": "Western enterprise client IT budget consolidation and delayed digital transformation contracts.",
                    "shocks": {
                        "tech_momentum_beta": -12.0,
                        "market_beta": -3.0,
                    },
                    "category": "industry_catalyst",
                },
                {
                    "id": "domestic_credit_spread_widening",
                    "name": "NBFC & Corporate Spread Widening (+150bps)",
                    "type": "Credit & Liquidity Squeeze",
                    "description": "Non-bank finance liquidity tightens, corporate bond yields widen +150bps over repo rate.",
                    "shocks": {
                        "credit_spread_beta": 7.5,
                        "market_beta": -4.8,
                    },
                    "category": "credit_liquidity",
                },
            ]
        else:
            scenarios_definitions = [
                {
                    "id": "fed_pivot_rate_spike",
                    "name": "Fed Pivot +50bps",
                    "type": "Interest Rate Spike",
                    "description": "Short rate hike (+50bps), yield curve shifts up, equity multiple compression.",
                    "shocks": {
                        "market_beta": -2.5,
                        "interest_rate_beta": 4.5,
                        "credit_spread_beta": 1.0,
                    },
                    "category": "macro_monetary",
                },
                {
                    "id": "global_recession_bear",
                    "name": "Global Recession (Bear)",
                    "type": "Consumer Confidence Drop",
                    "description": "Broad market equity liquidation, corporate earnings contraction (-18% market).",
                    "shocks": {
                        "market_beta": -18.0,
                        "credit_spread_beta": 4.0,
                        "oil_beta": -5.0,
                    },
                    "category": "macro_economic",
                },
                {
                    "id": "oil_supply_shock_120",
                    "name": "Oil Spike to $120",
                    "type": "Supply Chain Shock",
                    "description": "Crude oil surge +50% due to geopolitical disruption, input cost inflation.",
                    "shocks": {
                        "oil_beta": 12.0,
                        "market_beta": -4.0,
                        "interest_rate_beta": 1.5,
                    },
                    "category": "commodity_geopolitical",
                },
                {
                    "id": "ai_infra_expansion",
                    "name": "AI Infrastructure Expansion",
                    "type": "Catalyst Event",
                    "description": "Massive capital expenditure cycle acceleration in high-performance computing.",
                    "shocks": {
                        "tech_momentum_beta": 15.0,
                        "market_beta": 4.5,
                    },
                    "category": "industry_catalyst",
                },
                {
                    "id": "credit_spread_widening",
                    "name": "Credit Spread Widening (+200bps)",
                    "type": "Refinancing Crunch",
                    "description": "High yield spreads widen +200bps, debt refinancing costs surge.",
                    "shocks": {
                        "credit_spread_beta": 8.0,
                        "market_beta": -5.5,
                    },
                    "category": "credit_liquidity",
                },
                {
                    "id": "usd_liquidity_squeeze",
                    "name": "USD Dollar Surge (+10% DXY)",
                    "type": "FX Headwind",
                    "description": "Surging US dollar penalizes multinational foreign revenues.",
                    "shocks": {
                        "market_beta": -3.5,
                        "tech_momentum_beta": -4.0,
                    },
                    "category": "currency_fx",
                },
            ]

        results = []
        for s in scenarios_definitions:
            impact = 0.0
            factor_contributions = {}
            for factor_name, shock_magnitude in s["shocks"].items():
                sensitivity = sens.get(factor_name, 0.0)
                contribution = sensitivity * shock_magnitude
                factor_contributions[factor_name] = round(contribution, 2)
                impact += contribution

            impact_pct = round(impact, 1)
            status = "danger" if impact_pct < -5.0 else ("warning" if impact_pct < 0 else "success")

            results.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "type": s["type"],
                    "impact_pct": impact_pct,
                    "status": status,
                    "factor_breakdown": factor_contributions,
                    "narrative": s["description"],
                }
            )

        return results


