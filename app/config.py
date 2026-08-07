import os

from app.index_config import get_tracked_assets

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    def load_dotenv() -> bool:
        return False

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.getenv("APP_ENV", "local")
    DEBUG = _bool_env("FLASK_DEBUG", False)
    TESTING = _bool_env("TESTING", False)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-local-secret")

    SQLALCHEMY_DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://stock:stock@localhost:5432/stock_tracker",
    )

    DEFAULT_TICKER = os.getenv("DEFAULT_TICKER", "AAPL")
    DEFAULT_PERIOD = os.getenv("DEFAULT_PERIOD", "monthly")
    DEFAULT_PRICE_FIELD = os.getenv("DEFAULT_PRICE_FIELD", "adjusted_close")
    PRICE_DATA_DIR = "data/prices"
    DEFAULT_START_DATE = "2010-01-01"
    DEFAULT_INTERVAL = "1d"
    PREFERRED_PRICE_COLUMN = "Adj Close"
    # The assets below are shared with the ETF overview cards and Dash controls.
    TRACKED_ASSETS = get_tracked_assets()

