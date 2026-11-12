"""One NSE bulk or block deal, kept so the deals page can show history (NSE's archive file holds one day)."""

from datetime import date

from sqlalchemy import Date, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LargeDeal(Base):
    __tablename__ = "large_deals"
    __table_args__ = (
        UniqueConstraint("deal_date", "kind", "symbol", "client", "side", "quantity", "price", name="uq_large_deal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(5), nullable=False, comment="bulk or block")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="NSE symbol")
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client: Mapped[str] = mapped_column(String(200), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False, comment="BUY or SELL")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
