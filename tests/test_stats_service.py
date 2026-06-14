import pandas as pd
import pytest

from app.services.stats_service import (
    add_log2_regression,
    analyze_prices,
    calculate_exponential_regression,
    calculate_linear_regression,
    calculate_log2_regression,
    resample_prices,
)


def test_resample_prices_supports_all_long_term_periods():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-05", "2024-02-01", "2024-04-01"]),
            "open": [10.0, 11.0, 20.0, 30.0],
            "high": [12.0, 15.0, 22.0, 33.0],
            "low": [9.0, 10.0, 19.0, 29.0],
            "close": [11.0, 14.0, 21.0, 32.0],
            "adjusted_close": [10.5, 13.5, 20.5, 31.5],
            "volume": [100, 150, 200, 300],
        }
    )

    assert len(resample_prices(frame, "weekly")) == 3
    assert len(resample_prices(frame, "monthly")) == 3
    assert len(resample_prices(frame, "quarterly")) == 2
    assert len(resample_prices(frame, "yearly")) == 1


def test_resample_prices_monthly_uses_expected_aggregations():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-05", "2024-02-01"]),
            "open": [10.0, 11.0, 20.0],
            "high": [12.0, 15.0, 22.0],
            "low": [9.0, 10.0, 19.0],
            "close": [11.0, 14.0, 21.0],
            "adjusted_close": [10.5, 13.5, 20.5],
            "volume": [100, 150, 200],
        }
    )

    result = resample_prices(frame, "monthly")

    assert len(result) == 2
    assert result.iloc[0]["open"] == 10.0
    assert result.iloc[0]["high"] == 15.0
    assert result.iloc[0]["low"] == 9.0
    assert result.iloc[0]["close"] == 14.0
    assert result.iloc[0]["adjusted_close"] == 13.5
    assert result.iloc[0]["volume"] == 250


def test_log2_transformation_uses_selected_price_field():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "close": [4.0, 8.0, 16.0],
            "adjusted_close": [2.0, 4.0, 8.0],
            "volume": [100, 100, 100],
        }
    )

    result, regression = add_log2_regression(frame, "adjusted_close")

    assert regression is not None
    assert list(result["analysis_price"]) == [2.0, 4.0, 8.0]
    assert list(result["log2_price"]) == [1.0, 2.0, 3.0]


def test_regression_output_shape_includes_log_and_price_trends():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "close": [2.0, 4.0, 8.0],
            "adjusted_close": [2.0, 4.0, 8.0],
            "volume": [100, 100, 100],
        }
    )

    result, regression = add_log2_regression(frame, "adjusted_close")

    assert regression is not None
    assert regression.slope == pytest.approx(1.0)
    assert regression.intercept == pytest.approx(1.0)
    assert regression.r_squared == pytest.approx(1.0)
    assert len(result) == 3
    assert {"log2_price", "log2_trend", "price_trend", "log2_deviation"}.issubset(result.columns)
    assert list(result["price_trend"].round(8)) == [2.0, 4.0, 8.0]
    assert list(result["log2_deviation"].round(8)) == [0.0, 0.0, 0.0]


def test_missing_or_zero_prices_are_handled_safely():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]),
            "close": [2.0, 0.0, None, 16.0],
            "adjusted_close": [None, 0.0, None, 16.0],
            "volume": [100, 100, 100, 100],
        }
    )

    result, regression = add_log2_regression(frame, "adjusted_close")

    assert regression is not None
    assert list(result["analysis_price"]) == [2.0, 16.0]
    assert list(result["log2_price"]) == [1.0, 4.0]
    assert result["log2_price"].notna().all()


def test_analyze_prices_resamples_then_regresses():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-05", "2024-02-01"]),
            "open": [10.0, 11.0, 20.0],
            "high": [12.0, 15.0, 22.0],
            "low": [9.0, 10.0, 19.0],
            "close": [8.0, 16.0, 32.0],
            "adjusted_close": [8.0, 16.0, 32.0],
            "volume": [100, 150, 200],
        }
    )

    analysis = analyze_prices(frame, "monthly", "adjusted_close")

    assert analysis.regression is not None
    assert len(analysis.frame) == 2
    assert {"log2_trend", "price_trend", "log2_deviation"}.issubset(analysis.frame.columns)


def test_calculate_log2_regression_returns_parameters():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-10", "2024-01-20"]),
            "Adj Close": [100.0, 110.0, 125.0],
        }
    )

    result, params = calculate_log2_regression(frame)

    assert "Log2 Regression" in result.columns
    assert "a" in params
    assert "b" in params
    assert params["price_column"] == "Adj Close"


def test_calculate_log2_regression_avoids_log2_zero():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04"]),
            "Adj Close": [10.0, 11.0, 13.0],
        }
    )

    result, _ = calculate_log2_regression(frame)

    assert pd.Series(result["Log2 Regression"]).notna().all()
    assert pd.Series(result["Log2 Regression"]).map(lambda value: value != float("inf")).all()
    assert pd.Series(result["Log2 Regression"]).map(lambda value: value != float("-inf")).all()


def test_calculate_log2_regression_falls_back_to_close():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"]),
            "Close": [20.0, 22.0, 24.0],
        }
    )

    result, params = calculate_log2_regression(frame)

    assert "Log2 Regression" in result.columns
    assert params["price_column"] == "Close"


def test_calculate_log2_regression_requires_two_rows():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01"]),
            "Adj Close": [100.0],
        }
    )

    with pytest.raises(ValueError):
        calculate_log2_regression(frame)


def test_calculate_linear_regression_returns_predictions_and_params():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"]),
            "Close": [10.0, 14.0, 18.0],
        }
    )

    predictions, params = calculate_linear_regression(frame, "Close")

    assert isinstance(predictions, pd.Series)
    assert len(predictions) == 3
    assert params["type"] == "linear"
    assert "a" in params
    assert "b" in params
    assert params["row_count"] == 3


def test_calculate_exponential_regression_returns_predictions_and_params():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "Close": [2.0, 4.0, 8.0],
        }
    )

    predictions, params = calculate_exponential_regression(frame, "Close")

    assert isinstance(predictions, pd.Series)
    assert len(predictions) == 3
    assert params["type"] == "exponential"
    assert "a" in params
    assert "b" in params
    assert params["row_count"] == 3


def test_exponential_regression_rejects_non_positive_values_if_too_few_left():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "Close": [0.0, -2.0, 5.0],
        }
    )

    with pytest.raises(ValueError):
        calculate_exponential_regression(frame, "Close")


def test_regressions_ignore_nan_and_inf():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
            "Close": [10.0, float("nan"), 14.0, float("inf"), 18.0],
        }
    )

    linear_predictions, linear_params = calculate_linear_regression(frame, "Close")
    exponential_predictions, exponential_params = calculate_exponential_regression(frame, "Close")

    assert len(linear_predictions) == 3
    assert len(exponential_predictions) == 3
    assert linear_params["row_count"] == 3
    assert exponential_params["row_count"] == 3
