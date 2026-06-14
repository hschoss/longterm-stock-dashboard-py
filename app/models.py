from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    prices: Mapped[list["StockPrice"]] = relationship(back_populates="stock", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_stocks_symbol", "symbol"),)


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    stock: Mapped[Stock] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint("stock_id", "price_date", name="uq_stock_prices_stock_id_price_date"),
        Index("ix_stock_prices_stock_id_price_date", "stock_id", "price_date"),
    )
