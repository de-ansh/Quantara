"""Portfolio and Position models for user portfolio management."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Portfolio(Base):
    """Portfolio model representing a user's multi-asset portfolio."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_investment: Mapped[float] = mapped_column(Float, default=100000.0, nullable=False)

    # Relationships
    positions: Mapped[list["PortfolioPosition"]] = relationship(
        "PortfolioPosition",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, user_id={self.user_id}, name={self.name})>"


class PortfolioPosition(Base):
    """Position model representing an asset holding within a portfolio."""

    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker"), nullable=False, index=True
    )
    shares: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_basis: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Target portfolio weight (0.0 - 1.0)"
    )

    # Relationship
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="positions")

    def __repr__(self) -> str:
        return f"<PortfolioPosition(ticker={self.ticker}, weight={self.weight})>"
