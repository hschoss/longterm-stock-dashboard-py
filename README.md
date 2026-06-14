# Stock Tracker MVP

Minimal local Flask app for long-term single-stock analysis using PostgreSQL, SQLAlchemy, pandas, numpy, and Plotly.

## Dependency Format

This project uses `requirements.txt` because it is the simplest practical option for an MVP: one dependency file, direct `pip` support, and straightforward Docker builds.

## Required Environment

Create `.env` from the example before running Docker Compose:

```bash
cp .env.example .env
```

Required variables:

```text
APP_ENV=local
FLASK_DEBUG=false
SECRET_KEY=dev-only-local-secret
POSTGRES_DB=stock_tracker
POSTGRES_USER=stock
POSTGRES_PASSWORD=stock
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://stock:stock@postgres:5432/stock_tracker
WEB_PORT=5000
DEFAULT_TICKER=AAPL
DEFAULT_PERIOD=monthly
DEFAULT_PRICE_FIELD=adjusted_close
```

Inside Docker Compose, the database hostname is `postgres`, not `localhost`.

## Docker Compose Commands

**use sudo**

Build the Flask image:

```bash
docker compose build
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Initialize the database schema:

```bash
docker compose run --rm web python scripts/init_db.py
```

Seed demo data:

```bash
docker compose run --rm web python scripts/seed_demo_data.py
```

Start the Flask app:

```bash
docker compose up -d web
```

Open the app:

```text
http://127.0.0.1:5000
```

Run tests inside the app container:

```bash
docker compose run --rm web pytest
```

Stop containers while keeping PostgreSQL data:

```bash
docker compose down
```

Stop containers and remove PostgreSQL data:

```bash
docker compose down -v
```

## Local Python Tests

If you prefer running tests outside Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

The smoke tests use an in-memory SQLite database for speed. Runtime configuration remains PostgreSQL-oriented through `DATABASE_URL`.

## Database Initialization

`scripts/init_db.py` creates the current SQLAlchemy schema using `Base.metadata.create_all()`. This is intentionally simple for the MVP. A migration framework can be added later when schema evolution becomes important.

`scripts/seed_demo_data.py` inserts fake AAPL data only if the database has no stocks, so it is safe to run repeatedly.
