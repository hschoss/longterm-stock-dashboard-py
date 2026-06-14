from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from flask import current_app

try:
    import yfinance as yf
except ModuleNotFoundError:  # pragma: no cover - optional until download is used
    yf = None

try:
    from sqlalchemy import Select, select
    from sqlalchemy.orm import Session

    from app.models import Stock, StockPrice
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    Select = Any
    Session = Any
    Stock = Any
    StockPrice = Any
    select = None


def list_stocks(session: Session) -> list[Stock]:
    if select is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    return list(session.scalars(select(Stock).order_by(Stock.symbol)))


def get_stock(session: Session, symbol: str) -> Stock | None:
    if select is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    return session.scalar(select(Stock).where(Stock.symbol == symbol.upper()))


def get_price_frame(session: Session, stock: Stock, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
    if select is None:
        raise RuntimeError("SQLAlchemy is not installed in the current environment.")
    statement: Select[tuple] = (
        select(
            StockPrice.price_date,
            StockPrice.open,
            StockPrice.high,
            StockPrice.low,
            StockPrice.close,
            StockPrice.adjusted_close,
            StockPrice.volume,
        )
        .where(StockPrice.stock_id == stock.id)
        .order_by(StockPrice.price_date)
    )
    if start_date is not None:
        statement = statement.where(StockPrice.price_date >= start_date)
    if end_date is not None:
        statement = statement.where(StockPrice.price_date <= end_date)

    rows = session.execute(statement).all()
    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "adjusted_close", "volume"])
    if frame.empty:
        return frame

    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["open", "high", "low", "close", "adjusted_close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("int64")
    return frame


PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
REQUIRED_PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def get_asset_by_symbol(symbol: str) -> dict | None:
    normalized_symbol = symbol.strip().upper()
    for asset in current_app.config.get("TRACKED_ASSETS", []):
        asset_symbol = str(asset.get("symbol", "")).strip().upper()
        if asset_symbol == normalized_symbol:
            return asset
    return None


def get_price_csv_path(symbol: str) -> Path:
    configured_dir = Path(current_app.config["PRICE_DATA_DIR"])
    if not configured_dir.is_absolute():
        configured_dir = Path(current_app.root_path).parent / configured_dir
    configured_dir.mkdir(parents=True, exist_ok=True)
    safe_symbol = symbol.strip().replace("/", "_")
    return configured_dir / f"{safe_symbol}.csv"


def _is_placeholder_symbol(symbol: str) -> bool:
    return symbol.strip().upper().startswith("PLEASE_FILL_YFINANCE_SYMBOL")


def _flatten_download_columns(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    normalized_symbol = symbol.strip().upper()
    flattened_columns: list[str] = []
    for column in frame.columns.to_flat_index():
        parts = [str(part).strip() for part in column if str(part).strip()]
        price_part = next((part for part in parts if part in PRICE_COLUMNS), None)
        if price_part is not None:
            flattened_columns.append(price_part)
            continue

        non_symbol_parts = [part for part in parts if part.upper() != normalized_symbol]
        flattened_columns.append(non_symbol_parts[-1] if non_symbol_parts else parts[-1])

    flattened = frame.copy()
    flattened.columns = flattened_columns
    return flattened


def _normalize_price_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"No price data returned for symbol '{symbol}'.")

    normalized = _flatten_download_columns(frame, symbol).reset_index()
    if "index" in normalized.columns and "Date" not in normalized.columns:
        normalized = normalized.rename(columns={"index": "Date"})
    if "Datetime" in normalized.columns and "Date" not in normalized.columns:
        normalized = normalized.rename(columns={"Datetime": "Date"})

    if "Date" not in normalized.columns:
        raise ValueError(f"Downloaded data for '{symbol}' does not contain a Date column.")

    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce", utc=True).dt.tz_localize(None)
    normalized = normalized.dropna(subset=["Date"]).sort_values("Date")
    if normalized.empty:
        raise ValueError(f"Downloaded data for '{symbol}' does not contain valid rows.")

    for column in PRICE_COLUMNS:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "Volume" not in normalized.columns:
        normalized["Volume"] = 0

    missing_required = [column for column in REQUIRED_PRICE_COLUMNS if column not in normalized.columns]
    if missing_required:
        raise ValueError(
            f"Downloaded data for '{symbol}' is missing required columns: {', '.join(missing_required)}."
        )

    ordered_columns = [column for column in ["Date", *PRICE_COLUMNS] if column in normalized.columns]
    normalized = normalized[ordered_columns]
    if normalized[["Open", "High", "Low", "Close"]].dropna(how="all").empty:
        raise ValueError(f"Downloaded data for '{symbol}' does not contain usable OHLC prices.")

    normalized["Volume"] = pd.to_numeric(normalized["Volume"], errors="coerce").fillna(0).astype("int64")
    return normalized


def download_price_data(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str | None = None,
    overwrite: bool = True,
) -> pd.DataFrame:
    if _is_placeholder_symbol(symbol):
        raise ValueError(f"Symbol '{symbol}' is still a placeholder. Please replace it with a yfinance ticker.")
    if yf is None:
        raise ValueError("yfinance is not installed in the current environment.")

    csv_path = get_price_csv_path(symbol)
    if not overwrite and csv_path.exists():
        return load_price_data(symbol)

    download_start = start or current_app.config["DEFAULT_START_DATE"]
    download_interval = interval or current_app.config["DEFAULT_INTERVAL"]
    frame = yf.download(
        symbol,
        start=download_start,
        end=end,
        interval=download_interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    normalized = _normalize_price_frame(frame, symbol)
    normalized.to_csv(csv_path, index=False)
    return normalized


def load_price_data(symbol: str) -> pd.DataFrame:
    csv_path = get_price_csv_path(symbol)
    if not csv_path.exists():
        raise ValueError(f"No saved price data found for symbol '{symbol}'.")

    frame = pd.read_csv(csv_path, parse_dates=["Date"])
    return _normalize_price_frame(frame, symbol)


def ensure_price_data(symbol: str) -> pd.DataFrame:
    csv_path = get_price_csv_path(symbol)
    if csv_path.exists():
        return load_price_data(symbol)
    return download_price_data(symbol, overwrite=True)
