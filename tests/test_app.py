from pathlib import Path

from app import create_app


class TestConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    DEFAULT_TICKER = "TESTETF"
    DEFAULT_PERIOD = "monthly"
    DEFAULT_PRICE_FIELD = "adjusted_close"
    PRICE_DATA_DIR = "data/test-prices"
    DEFAULT_START_DATE = "2020-01-01"
    DEFAULT_INTERVAL = "1d"
    PREFERRED_PRICE_COLUMN = "Adj Close"
    TRACKED_ASSETS = [
        {
            "name": "Test ETF",
            "symbol": "TESTETF",
            "wkn": "TEST01",
            "isin": "TESTISIN0001",
            "index": "Test Index",
            "provider": "Test Provider",
            "distribution": "acc",
            "map_label": "Test Region",
            "lat": 48.0,
            "lon": 11.0,
            "region": "Europe",
        }
    ]


def build_test_app():
    app = create_app(TestConfig)
    with app.app_context():
        price_dir = Path(app.root_path).parent / TestConfig.PRICE_DATA_DIR
        price_dir.mkdir(parents=True, exist_ok=True)
        csv_path = price_dir / "TESTETF.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "Date,Open,High,Low,Close,Adj Close,Volume",
                    "2024-01-01,100,105,99,102,101,1000",
                    "2024-01-10,102,108,101,107,106,1200",
                    "2024-01-20,107,112,106,111,110,1400",
                ]
            ),
            encoding="utf-8",
        )
    return app


def test_index_route_smoke():
    client = build_test_app().test_client()

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dash/")


def test_create_app_smoke():
    app = build_test_app()

    assert app is not None


def test_stocks_route_smoke():
    client = build_test_app().test_client()

    response = client.get("/stocks")

    assert response.status_code == 200
    assert b"TESTETF" in response.data
    assert b"TEST01" in response.data


def test_stock_detail_route_smoke():
    client = build_test_app().test_client()

    response = client.get("/stocks/TESTETF")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dash/assets/TESTETF")


def test_dash_root_route_smoke():
    client = build_test_app().test_client()

    response = client.get("/dash/")

    assert response.status_code == 200
    assert b"Longterm Stock Dashboard" in response.data


def test_dash_asset_route_smoke():
    client = build_test_app().test_client()

    response = client.get("/dash/assets/TESTETF")

    assert response.status_code == 200
    assert b"Longterm Stock Dashboard" in response.data
