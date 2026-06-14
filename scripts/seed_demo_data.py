from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app import create_app
from app.extensions import get_engine, session_scope
from app.models import Base, Stock, StockPrice


def seed_demo_data() -> None:
    app = create_app()
    with app.app_context():
        Base.metadata.create_all(get_engine())
        with session_scope() as session:
            stock_count = session.scalar(select(func.count(Stock.id))) or 0
            if stock_count:
                print("Database already contains stocks; skipping demo seed.")
                return

            stock = Stock(symbol="AAPL", name="Demo Apple Inc.", exchange="NASDAQ", currency="USD")
            session.add(stock)
            session.flush()

            start = date(2020, 1, 2)
            base_price = Decimal("75.00")
            for index in range(160):
                current_date = start + timedelta(days=index * 7)
                drift = Decimal(index) * Decimal("0.42")
                wave = Decimal(index % 9) * Decimal("0.35")
                close = base_price + drift + wave
                adjusted_close = close * Decimal("0.985")
                session.add(
                    StockPrice(
                        stock_id=stock.id,
                        price_date=current_date,
                        open=close - Decimal("0.75"),
                        high=close + Decimal("1.25"),
                        low=close - Decimal("1.50"),
                        close=close,
                        adjusted_close=adjusted_close,
                        volume=90_000_000 + index * 100_000,
                    )
                )
            print("Inserted demo stock data for AAPL.")


if __name__ == "__main__":
    seed_demo_data()
