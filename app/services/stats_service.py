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


def _resolve_price_column(df: pd.DataFrame, price_column: str) -> str:
    if price_column in df.columns:
        return price_column
    if price_column == "Adj Close" and "Close" in df.columns:
        return "Close"
    raise ValueError(f"Price column '{price_column}' is not available.")


def normalize_price_series_to_100(
    df: pd.DataFrame,
    price_column: str,
) -> pd.DataFrame:
    if df.empty:
        raise ValueError("Price data is empty.")
    if "Date" not in df.columns:
        raise ValueError("Price data must contain a Date column.")

    actual_price_column = _resolve_price_column(df, price_column)
    working = df.copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working = working.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    working[actual_price_column] = pd.to_numeric(working[actual_price_column], errors="coerce")
    finite_mask = np.isfinite(working[actual_price_column].to_numpy(dtype=float))
    working = working.loc[finite_mask].copy()
    working = working[working[actual_price_column] > 0].copy()

    if len(working) < 2:
        raise ValueError("At least two valid positive price rows are required for normalization.")

    first_valid_price = float(working[actual_price_column].iloc[0])
    if first_valid_price <= 0 or not np.isfinite(first_valid_price):
        raise ValueError("The first valid price must be positive and finite.")

    working["Relative Value"] = working[actual_price_column] / first_valid_price * 100.0
    working.attrs["price_column"] = actual_price_column
    return working


def align_two_normalized_series(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    price_column: str,
) -> tuple[pd.DataFrame, str]:
    if "Date" not in left_df.columns or "Date" not in right_df.columns:
        raise ValueError("Both price series must contain a Date column.")

    left_column = _resolve_price_column(left_df, price_column)
    right_column = _resolve_price_column(right_df, price_column)
    if left_column != right_column:
        if {left_column, right_column} == {"Adj Close", "Close"}:
            actual_price_column = "Close"
        else:
            raise ValueError("Both assets must support the same comparable price column.")
    else:
        actual_price_column = left_column

    left_working = left_df.copy()
    right_working = right_df.copy()
    left_working["Date"] = pd.to_datetime(left_working["Date"], errors="coerce")
    right_working["Date"] = pd.to_datetime(right_working["Date"], errors="coerce")
    left_working = left_working.dropna(subset=["Date"]).sort_values("Date")
    right_working = right_working.dropna(subset=["Date"]).sort_values("Date")

    for frame in (left_working, right_working):
        frame[actual_price_column] = pd.to_numeric(frame[actual_price_column], errors="coerce")

    left_working = left_working[np.isfinite(left_working[actual_price_column].to_numpy(dtype=float))]
    right_working = right_working[np.isfinite(right_working[actual_price_column].to_numpy(dtype=float))]
    left_working = left_working[left_working[actual_price_column] > 0]
    right_working = right_working[right_working[actual_price_column] > 0]

    aligned = left_working[["Date", actual_price_column]].merge(
        right_working[["Date", actual_price_column]],
        on="Date",
        how="inner",
        suffixes=("_left", "_right"),
    )
    aligned = aligned.sort_values("Date").reset_index(drop=True)
    if len(aligned) < 2:
        raise ValueError("At least two common valid price points are required for comparison.")

    left_base = float(aligned[f"{actual_price_column}_left"].iloc[0])
    right_base = float(aligned[f"{actual_price_column}_right"].iloc[0])
    aligned["Left Relative Value"] = aligned[f"{actual_price_column}_left"] / left_base * 100.0
    aligned["Right Relative Value"] = aligned[f"{actual_price_column}_right"] / right_base * 100.0
    return aligned[["Date", "Left Relative Value", "Right Relative Value"]], actual_price_column


def _resolve_price_column(df: pd.DataFrame, price_column: str) -> str:
    if price_column in df.columns:
        return price_column
    if price_column == "Adj Close" and "Close" in df.columns:
        return "Close"
    raise ValueError(f"Price column '{price_column}' is not available.")


def normalize_price_series_to_100(
    df: pd.DataFrame,
    price_column: str,
) -> pd.DataFrame:
    if df.empty:
        raise ValueError("Price data is empty.")
    if "Date" not in df.columns:
        raise ValueError("Price data must contain a Date column.")

    actual_price_column = _resolve_price_column(df, price_column)
    working = df.copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working = working.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    working[actual_price_column] = pd.to_numeric(working[actual_price_column], errors="coerce")
    finite_mask = np.isfinite(working[actual_price_column].to_numpy(dtype=float))
    working = working.loc[finite_mask].copy()
    working = working[working[actual_price_column] > 0].copy()

    if len(working) < 2:
        raise ValueError("At least two valid positive price rows are required for normalization.")

    first_valid_price = float(working[actual_price_column].iloc[0])
    if first_valid_price <= 0 or not np.isfinite(first_valid_price):
        raise ValueError("The first valid price must be positive and finite.")

    working["Relative Value"] = working[actual_price_column] / first_valid_price * 100.0
    working.attrs["price_column"] = actual_price_column
    return working


def align_two_normalized_series(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    price_column: str,
) -> tuple[pd.DataFrame, str]:
    if "Date" not in left_df.columns or "Date" not in right_df.columns:
        raise ValueError("Both price series must contain a Date column.")

    requested_column = price_column
    left_column = _resolve_price_column(left_df, requested_column)
    right_column = _resolve_price_column(right_df, requested_column)
    if left_column != right_column:
        if {left_column, right_column} == {"Adj Close", "Close"}:
            actual_price_column = "Close"
        else:
            raise ValueError("Both assets must support the same comparable price column.")
    else:
        actual_price_column = left_column

    left_working = left_df.copy()
    right_working = right_df.copy()
    left_working["Date"] = pd.to_datetime(left_working["Date"], errors="coerce")
    right_working["Date"] = pd.to_datetime(right_working["Date"], errors="coerce")
    left_working = left_working.dropna(subset=["Date"]).sort_values("Date")
    right_working = right_working.dropna(subset=["Date"]).sort_values("Date")

    for frame in (left_working, right_working):
        frame[actual_price_column] = pd.to_numeric(frame[actual_price_column], errors="coerce")

    left_working = left_working[np.isfinite(left_working[actual_price_column].to_numpy(dtype=float))]
    right_working = right_working[np.isfinite(right_working[actual_price_column].to_numpy(dtype=float))]
    left_working = left_working[left_working[actual_price_column] > 0]
    right_working = right_working[right_working[actual_price_column] > 0]

    aligned = left_working[["Date", actual_price_column]].merge(
        right_working[["Date", actual_price_column]],
        on="Date",
        how="inner",
        suffixes=("_left", "_right"),
    )
    aligned = aligned.sort_values("Date").reset_index(drop=True)
    if len(aligned) < 2:
        raise ValueError("At least two common valid price points are required for comparison.")

    left_base = float(aligned[f"{actual_price_column}_left"].iloc[0])
    right_base = float(aligned[f"{actual_price_column}_right"].iloc[0])
    aligned["Left Relative Value"] = aligned[f"{actual_price_column}_left"] / left_base * 100.0
    aligned["Right Relative Value"] = aligned[f"{actual_price_column}_right"] / right_base * 100.0
    return aligned[["Date", "Left Relative Value", "Right Relative Value"]], actual_price_column
