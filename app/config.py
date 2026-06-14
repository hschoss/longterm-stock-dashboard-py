import os

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
    # The map markers below are representative anchor points for ETF/index regions,
    # not precise headquarters or constituent-company locations.
    TRACKED_ASSETS = [
        {
            "name": "iShares STOXX Europe 600 UCITS ETF (DE)",
            "symbol": "EXSA.DE",
            "wkn": "263530",
            "isin": "DE0002635307",
            "index": "STOXX Europe 600",
            "provider": "iShares",
            "distribution": "dist",
            "map_label": "Europe",
            "lat": 50.1109,
            "lon": 8.6821,
            "region": "Europe",
        },
        {
            "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",
            "symbol": "SXR8.DE",
            "wkn": "A0YEDG",
            "isin": "IE00B5BMR087",
            "index": "S&P 500",
            "provider": "iShares",
            "distribution": "acc",
            "map_label": "USA",
            "lat": 39.8283,
            "lon": -98.5795,
            "region": "North America",
        },
        {
            "name": "iShares MSCI Canada UCITS ETF USD (Acc)",
            "symbol": "CCAU.L",
            "wkn": "A0YEDS",
            "isin": "IE00B52SF786",
            "index": "MSCI Canada",
            "provider": "iShares",
            "distribution": "acc",
            "map_label": "Canada",
            "lat": 56.1304,
            "lon": -106.3468,
            "region": "North America",
        },
        {
            "name": "iShares MSCI Japan UCITS ETF USD (Dist)",
            "symbol": "IQQJ.DE",
            "alternative_symbol": "IJPN.L",
            "wkn": "A0DK60",
            "isin": "IE00B02KXH56",
            "index": "MSCI Japan",
            "provider": "iShares",
            "distribution": "dist",
            "map_label": "Japan",
            "lat": 36.2048,
            "lon": 138.2529,
            "region": "Asia",
        },
        {
            "name": "Xtrackers MSCI Emerging Markets UCITS ETF 1C",
            "symbol": "XMME.DE",
            "wkn": "A12GVR",
            "isin": "IE00BTJRMP35",
            "index": "MSCI Emerging Markets",
            "provider": "Xtrackers",
            "distribution": "acc",
            "map_label": "Emerging Markets",
            "lat": 20.0,
            "lon": 80.0,
            "region": "Global Emerging Markets",
        },
    ]
