from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Period = Literal["weekly", "monthly", "quarterly", "yearly"]
PriceField = Literal["close", "adjusted_close"]

RESAMPLE_RULES: dict[str, str] = {
    "weekly": "W",
    "monthly": "ME",
    "quarterly": "QE",
    "yearly": "YE",
}

PRICE_FIELDS = {"close", "adjusted_close"}


@dataclass(frozen=True)
class RegressionResult:
    slope: float
    intercept: float
    r_squared: float


@dataclass(frozen=True)
class AnalysisResult:
    frame: pd.DataFrame
    regression: RegressionResult | None


def resample_prices(frame: pd.DataFrame, period: Period) -> pd.DataFrame:
    if period not in RESAMPLE_RULES:
        raise ValueError(f"Unsupported period: {period}")
    if frame.empty:
        return frame.copy()

    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"]).sort_values("date")
    if working.empty:
        return working

    for column in ["open", "high", "low", "close", "adjusted_close"]:
        if column in working:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    if "volume" in working:
        working["volume"] = pd.to_numeric(working["volume"], errors="coerce").fillna(0)

    indexed = working.set_index("date")
    resampled = indexed.resample(RESAMPLE_RULES[period]).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "adjusted_close": "last",
            "volume": "sum",
        }
    )
    return resampled.dropna(subset=["close"]).reset_index()


def add_log2_regression(frame: pd.DataFrame, price_field: PriceField = "adjusted_close") -> tuple[pd.DataFrame, RegressionResult | None]:
    if price_field not in PRICE_FIELDS:
        raise ValueError(f"Unsupported price field: {price_field}")
    if frame.empty:
        return frame.copy(), None

    working = frame.copy()
    price = pd.to_numeric(working[price_field], errors="coerce")
    if price_field == "adjusted_close":
        price = price.fillna(pd.to_numeric(working["close"], errors="coerce"))

    working["analysis_price"] = price
    working = working[working["analysis_price"] > 0].copy()
    if working.empty:
        return working, None

    working["log2_price"] = np.log2(working["analysis_price"].astype(float))
    x_values = np.arange(len(working), dtype=float)
    y_values = working["log2_price"].to_numpy(dtype=float)

    if len(working) < 2:
        working["log2_trend"] = y_values
        working["price_trend"] = np.power(2.0, y_values)
        working["log2_deviation"] = 0.0
        return working, None

    slope, intercept = np.polyfit(x_values, y_values, deg=1)
    log2_trend = slope * x_values + intercept
    residuals = y_values - log2_trend
    total_sum_squares = float(np.sum((y_values - np.mean(y_values)) ** 2))
    residual_sum_squares = float(np.sum(residuals**2))
    r_squared = 1.0 - residual_sum_squares / total_sum_squares if total_sum_squares else 1.0

    working["log2_trend"] = log2_trend
    working["price_trend"] = np.power(2.0, log2_trend)
    working["log2_deviation"] = residuals
    return working, RegressionResult(slope=float(slope), intercept=float(intercept), r_squared=float(r_squared))


def analyze_prices(frame: pd.DataFrame, period: Period, price_field: PriceField) -> AnalysisResult:
    resampled = resample_prices(frame, period)
    analyzed, regression = add_log2_regression(resampled, price_field)
    return AnalysisResult(frame=analyzed, regression=regression)


def calculate_log2_regression(
    df: pd.DataFrame,
    price_column: str = "Adj Close",
) -> tuple[pd.DataFrame, dict[str, float | str | int]]:
    if df.empty:
        raise ValueError("Price data is empty.")

    selected_price_column = price_column
    if selected_price_column not in df.columns:
        if selected_price_column == "Adj Close" and "Close" in df.columns:
            selected_price_column = "Close"
        else:
            raise ValueError(f"Price column '{price_column}' is not available.")

    working = df.copy()
    if "Date" in working.columns:
        working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
        working = working.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        if working.empty:
            raise ValueError("Price data does not contain valid dates.")

    working[selected_price_column] = pd.to_numeric(working[selected_price_column], errors="coerce")
    finite_mask = np.isfinite(working[selected_price_column].to_numpy(dtype=float))
    working = working.loc[finite_mask].copy()
    if len(working) < 2:
        raise ValueError("At least two valid price rows are required for log2 regression.")

    if "Date" in working.columns:
        days_since_start = (working["Date"] - working["Date"].iloc[0]).dt.days.to_numpy(dtype=float)
    else:
        days_since_start = np.arange(len(working), dtype=float)

    x_safe = days_since_start + 1.0
    log2_x = np.log2(x_safe)
    y_values = working[selected_price_column].to_numpy(dtype=float)

    if not np.isfinite(log2_x).all():
        raise ValueError("Log2 regression input contains invalid x values.")
    if not np.isfinite(y_values).all():
        raise ValueError("Log2 regression input contains invalid price values.")

    a, b = np.polyfit(log2_x, y_values, deg=1)
    regression_values = a * log2_x + b
    if not np.isfinite(regression_values).all():
        raise ValueError("Log2 regression produced invalid values.")

    working["Log2 Regression"] = regression_values
    return working, {
        "a": float(a),
        "b": float(b),
        "price_column": selected_price_column,
        "row_count": int(len(working)),
    }


def _prepare_regression_frame(
    df: pd.DataFrame,
    price_column: str,
    *,
    positive_only: bool = False,
) -> tuple[pd.DataFrame, np.ndarray]:
    if df.empty:
        raise ValueError("Price data is empty.")
    if price_column not in df.columns:
        raise ValueError(f"Price column '{price_column}' is not available.")

    working = df.copy()
    if "Date" in working.columns:
        working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
        working = working.dropna(subset=["Date"]).sort_values("Date")

    working[price_column] = pd.to_numeric(working[price_column], errors="coerce")
    finite_mask = np.isfinite(working[price_column].to_numpy(dtype=float))
    working = working.loc[finite_mask].copy()
    if positive_only:
        working = working[working[price_column] > 0].copy()

    if len(working) < 2:
        raise ValueError("At least two valid price rows are required for regression.")

    if "Date" in working.columns:
        days_since_start = (working["Date"] - working["Date"].iloc[0]).dt.days.to_numpy(dtype=float)
    else:
        days_since_start = np.arange(len(working), dtype=float)

    if np.unique(days_since_start).size < 2:
        raise ValueError("At least two distinct x values are required for regression.")

    return working, days_since_start


def calculate_linear_regression(
    df: pd.DataFrame,
    price_column: str,
) -> tuple[pd.Series, dict[str, float | str | int]]:
    working, x_values = _prepare_regression_frame(df, price_column)
    y_values = working[price_column].to_numpy(dtype=float)

    a, b = np.polyfit(x_values, y_values, deg=1)
    predictions = pd.Series(a * x_values + b, index=working.index, name="Linear Regression")
    return predictions, {
        "type": "linear",
        "a": float(a),
        "b": float(b),
        "row_count": int(len(working)),
    }


def calculate_exponential_regression(
    df: pd.DataFrame,
    price_column: str,
) -> tuple[pd.Series, dict[str, float | str | int]]:
    working, x_values = _prepare_regression_frame(df, price_column, positive_only=True)
    y_values = working[price_column].to_numpy(dtype=float)

    log_y_values = np.log(y_values)
    b, log_a = np.polyfit(x_values, log_y_values, deg=1)
    a = float(np.exp(log_a))
    predictions = pd.Series(a * np.exp(b * x_values), index=working.index, name="Exponential Regression")
    return predictions, {
        "type": "exponential",
        "a": a,
        "b": float(b),
        "row_count": int(len(working)),
    }
