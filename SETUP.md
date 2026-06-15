# App Setup and Takedown

This project can be run in two supported ways:

1. Local Python runtime with a SQLite database file.
2. Docker Compose with PostgreSQL.

The local path is the simplest way to get the app running on `http://127.0.0.1:5000`.

## Local Setup

### Prerequisites

- Python virtualenv available at `.venv`
- Project dependencies installed in `.venv`

If the virtualenv does not exist yet:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Initialize a local database

Run the schema setup against a local SQLite file:

```bash
env DATABASE_URL=sqlite:////home/hannes/gh/longterm-stock-dashboard-py/local.db ./.venv/bin/python scripts/init_db.py
```

This creates `local.db` in the repository root.

### Start the app on port 5000

```bash
env DATABASE_URL=sqlite:////home/hannes/gh/longterm-stock-dashboard-py/local.db ./.venv/bin/flask --app app:create_app run --host 127.0.0.1 --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

Expected behavior:

- `/` redirects to `/dash/`
- the Dash UI loads at `/dash/`

### Take the local app down

If the Flask process is running in the current terminal, press `Ctrl+C`.

If you need to stop it from another terminal:

```bash
pkill -f "flask --app app:create_app run --host 127.0.0.1 --port 5000"
```

Optional cleanup:

```bash
rm -f local.db
```

Only remove `local.db` if you want to delete the local SQLite data.

## Docker Compose Setup

This path uses PostgreSQL and matches the repo's `.env` defaults.

### Prerequisites

- Docker installed
- permission to run Docker commands
- `.env` present in the repo root

If needed:

```bash
cp .env.example .env
```

The default `.env` values already map the web app to port `5000`.

### Start the stack

The current repo README expects `sudo` for Docker commands:

```bash
sudo docker compose build
sudo docker compose up -d postgres
sudo docker compose run --rm web python scripts/init_db.py
sudo docker compose run --rm web python scripts/seed_demo_data.py
sudo docker compose up -d web
```

Open:

```text
http://127.0.0.1:5000
```

### Take the Docker app down

Stop the containers but keep PostgreSQL data:

```bash
sudo docker compose down
```

Stop the containers and remove PostgreSQL data:

```bash
sudo docker compose down -v
```

## Verification

Quick HTTP check after startup:

```bash
curl -I http://127.0.0.1:5000
```

Expected result:

- `HTTP/1.1 302 FOUND`
- `Location: /dash/`

## Notes

- The local runtime uses the CSV files under `data/prices/` for the dashboard views.
- The Docker runtime uses PostgreSQL as configured by `DATABASE_URL` in `.env`.
- If port `5000` is already in use, stop the existing process before starting the app again.
