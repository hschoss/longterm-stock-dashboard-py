import numpy as np
import pandas as pd

from app.dash_apps.main_dash import (
    build_asset_figure,
    build_asset_y_slider_state,
    build_world_map_figure,
    parse_compare_symbols_from_search,
    parse_symbol_from_pathname,
)


def test_parse_symbol_from_pathname_returns_symbol_for_detail_route():
    assert parse_symbol_from_pathname("/dash/assets/SXR8.DE") == "SXR8.DE"


def test_parse_symbol_from_pathname_returns_none_for_non_detail_route():
    assert parse_symbol_from_pathname("/dash/") is None
    assert parse_symbol_from_pathname("/stocks/SXR8.DE") is None


def test_parse_compare_symbols_from_search_returns_symbols():
    left, right = parse_compare_symbols_from_search("?left=SXR8.DE&right=EXSA.DE")

    assert left == "SXR8.DE"
    assert right == "EXSA.DE"


def test_build_world_map_figure_contains_marker_per_mapped_asset():
    assets = [
        {"symbol": "AAA", "name": "Alpha", "region": "Europe", "lat": 50.0, "lon": 8.0},
        {"symbol": "BBB", "name": "Beta", "region": "Asia", "lat": 35.0, "lon": 139.0},
        {"symbol": "CCC", "name": "Gamma", "region": "Unknown", "lat": None, "lon": None},
    ]

    figure = build_world_map_figure(assets)

    assert len(figure.data) == 1
    trace = figure.data[0]
    assert len(trace.lat) == 2
    assert len(trace.lon) == 2
    assert list(trace.customdata) == ["AAA", "BBB"]
    assert np.isclose(trace.lat[0], 50.0)


def test_build_asset_figure_applies_requested_y_axis_range():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "Close": [10.0, 15.0, 20.0],
        }
    )

    figure, regression_meta = build_asset_figure(
        frame,
        symbol="TEST",
        price_column="Close",
        y_scale="linear",
        regression_type="none",
        start_idx=0,
        end_idx=2,
        y_axis_range=[11.0, 18.0],
    )

    assert regression_meta is None
    assert tuple(figure.layout.yaxis.range) == (11.0, 18.0)


def test_build_asset_y_slider_state_expands_flat_series_bounds():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "Close": [100.0, 100.0, 100.0],
        }
    )

    min_value, max_value, value, marks, step = build_asset_y_slider_state(
        frame,
        price_column="Close",
        y_scale="linear",
        regression_type="none",
        start_idx=0,
        end_idx=2,
    )

    assert min_value < 100.0
    assert max_value > 100.0
    assert value == [min_value, max_value]
    assert len(marks) >= 2
    assert step > 0

