import numpy as np

from app.dash_apps.main_dash import build_world_map_figure, parse_symbol_from_pathname


def test_parse_symbol_from_pathname_returns_symbol_for_detail_route():
    assert parse_symbol_from_pathname("/dash/assets/SXR8.DE") == "SXR8.DE"


def test_parse_symbol_from_pathname_returns_none_for_non_detail_route():
    assert parse_symbol_from_pathname("/dash/") is None
    assert parse_symbol_from_pathname("/stocks/SXR8.DE") is None


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
