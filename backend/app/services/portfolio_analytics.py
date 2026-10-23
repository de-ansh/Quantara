"""
Portfolio Analytics Engine - Covariance, Correlation, and Risk Computation.

Implements Markowitz Modern Portfolio Theory (MPT) calculations:
- Pairwise asset correlation and covariance matrix estimation
- True portfolio volatility computation: sigma_p = sqrt(w^T * Sigma * w)
- Diversification benefit quantification: (weighted_vol - portfolio_vol) / weighted_vol * 100%
- Asset-class and cross-sector correlation modeling
"""

import math
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


# Standard asset classification mappings
CASH_TICKERS = {"BIL", "SHV", "SGOV", "CASH", "USDOLLAR", "MINT", "ICSH"}
BOND_TICKERS = {"TLT", "BND", "AGG", "IEF", "SHY", "LQD", "HYG", "TIP", "BNDX"}
COMMODITY_TICKERS = {"GLD", "SLV", "IAU", "USO", "DBC", "GSG", "PDBC", "UNG"}


@dataclass
class PortfolioAnalyticsResult:
    """Computed portfolio metrics."""

    portfolio_return: float
    portfolio_volatility: float
    diversification_benefit_pct: float
    asset_volatilities: dict[str, float]
    correlation_matrix: dict[str, dict[str, float]]
    covariance_matrix: list[list[float]]
    tickers: list[str]
    normalized_weights: list[float]


class PortfolioAnalyticsEngine:
    """Engine for computing multi-asset portfolio covariance and risk metrics."""

    @staticmethod
    def classify_asset(ticker: str, sector: str | None = None) -> tuple[str, str | None]:
        """
        Classify ticker into broad asset class and sector.

        Returns:
            Tuple of (asset_class, sector_or_subclass)
            Asset classes: 'cash', 'fixed_income', 'commodity', 'equity'
        """
        t = ticker.upper()
        if t in CASH_TICKERS:
            return "cash", "Cash Equivalents"
        if t in BOND_TICKERS:
            return "fixed_income", "Sovereign/Corporate Debt"
        if t in COMMODITY_TICKERS:
            return "commodity", "Precious Metals/Commodities"
        return "equity", sector or "General Equities"

    @classmethod
    def estimate_pairwise_correlation(
        cls,
        ticker_a: str,
        ticker_b: str,
        sector_a: str | None = None,
        sector_b: str | None = None,
    ) -> float:
        """
        Estimate correlation coefficient between two assets.

        Range: -1.0 to 1.0.
        """
        t_a, t_b = ticker_a.upper(), ticker_b.upper()

        # Identical asset
        if t_a == t_b:
            return 1.0

        class_a, sec_a = cls.classify_asset(t_a, sector_a)
        class_b, sec_b = cls.classify_asset(t_b, sector_b)

        # Cash has zero correlation with risky assets
        if class_a == "cash" or class_b == "cash":
            return 0.0

        # Fixed Income vs Equities: negative co-movement (flight to safety)
        if (class_a == "fixed_income" and class_b == "equity") or (
            class_a == "equity" and class_b == "fixed_income"
        ):
            return -0.20

        # Commodities vs Equities: low positive correlation
        if (class_a == "commodity" and class_b == "equity") or (
            class_a == "equity" and class_b == "commodity"
        ):
            return 0.12

        # Commodities vs Fixed Income: modest positive correlation
        if (class_a == "commodity" and class_b == "fixed_income") or (
            class_a == "fixed_income" and class_b == "commodity"
        ):
            return 0.15

        # Intra-class correlations
        if class_a == "fixed_income" and class_b == "fixed_income":
            return 0.82

        if class_a == "commodity" and class_b == "commodity":
            return 0.65

        # Both are equities
        if class_a == "equity" and class_b == "equity":
            if sec_a and sec_b and sec_a.lower() == sec_b.lower():
                # Intra-sector (e.g. Technology stocks)
                return 0.72
            # Inter-sector
            return 0.45

        return 0.30

    @classmethod
    def build_correlation_matrix(
        cls,
        tickers: list[str],
        sectors: dict[str, str | None] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Build symmetric NxN correlation matrix for given tickers.
        """
        sectors = sectors or {}
        matrix: dict[str, dict[str, float]] = {}

        for t_a in tickers:
            matrix[t_a] = {}
            for t_b in tickers:
                sec_a = sectors.get(t_a)
                sec_b = sectors.get(t_b)
                corr = cls.estimate_pairwise_correlation(t_a, t_b, sec_a, sec_b)
                matrix[t_a][t_b] = round(corr, 4)

        return matrix

    @classmethod
    def calculate_portfolio_metrics(
        cls,
        tickers: list[str],
        weights: list[float],
        volatilities: list[float],
        expected_returns: list[float],
        sectors: dict[str, str | None] | None = None,
        custom_correlations: dict[str, dict[str, float]] | None = None,
    ) -> PortfolioAnalyticsResult:
        """
        Calculate complete portfolio risk and return using MPT covariance matrix.

        Args:
            tickers: List of stock symbols
            weights: Raw allocation weights
            volatilities: Annualized volatility per asset
            expected_returns: Annualized expected return per asset
            sectors: Optional ticker to sector mapping
            custom_correlations: Optional precomputed correlation matrix

        Returns:
            PortfolioAnalyticsResult with true portfolio volatility and matrices
        """
        n = len(tickers)
        if n == 0:
            return PortfolioAnalyticsResult(
                portfolio_return=0.0,
                portfolio_volatility=0.0,
                diversification_benefit_pct=0.0,
                asset_volatilities={},
                correlation_matrix={},
                covariance_matrix=[],
                tickers=[],
                normalized_weights=[],
            )

        # 1. Normalize weights
        total_weight = sum(weights)
        if total_weight <= 0:
            norm_weights = [1.0 / n] * n
        else:
            norm_weights = [w / total_weight for w in weights]

        # 2. Portfolio return: linear combination w^T * mu
        port_return = sum(w * r for w, r in zip(norm_weights, expected_returns, strict=True))

        # 3. Correlation matrix R
        corr_matrix = custom_correlations or cls.build_correlation_matrix(tickers, sectors)

        # 4. Covariance matrix Sigma: Sigma_ij = rho_ij * sigma_i * sigma_j
        cov_matrix: list[list[float]] = []
        for i in range(n):
            row: list[float] = []
            for j in range(n):
                t_i, t_j = tickers[i], tickers[j]
                rho = corr_matrix.get(t_i, {}).get(t_j, 1.0 if i == j else 0.4)
                cov = rho * volatilities[i] * volatilities[j]
                row.append(round(cov, 6))
            cov_matrix.append(row)

        # 5. Portfolio variance: w^T * Sigma * w
        port_variance = 0.0
        for i in range(n):
            for j in range(n):
                port_variance += norm_weights[i] * norm_weights[j] * cov_matrix[i][j]

        # Safeguard against floating point negative variance
        port_variance = max(1e-6, port_variance)
        port_volatility = math.sqrt(port_variance)

        # 6. Weighted average volatility (volatility assuming correlation = 1.0)
        weighted_vol = sum(w * v for w, v in zip(norm_weights, volatilities, strict=True))

        # 7. Diversification benefit percentage
        if weighted_vol > 0:
            diversification_benefit = max(
                0.0, ((weighted_vol - port_volatility) / weighted_vol) * 100.0
            )
        else:
            diversification_benefit = 0.0

        asset_vols = {
            tickers[i]: round(volatilities[i], 4) for i in range(n)
        }

        return PortfolioAnalyticsResult(
            portfolio_return=round(port_return, 6),
            portfolio_volatility=round(port_volatility, 6),
            diversification_benefit_pct=round(diversification_benefit, 2),
            asset_volatilities=asset_vols,
            correlation_matrix=corr_matrix,
            covariance_matrix=cov_matrix,
            tickers=tickers,
            normalized_weights=[round(w, 4) for w in norm_weights],
        )
