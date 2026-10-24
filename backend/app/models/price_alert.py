"""Price alert model: notify a user when a stock crosses a target price."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceAlert(Base):
    """One-shot alert; `triggered_at` is set the first time the condition holds."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.ticker"), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False, comment="above | below")
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    triggered_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<PriceAlert({self.ticker} {self.direction} {self.target_price})>"
