import numpy as np
import pandas as pd
from flask import Flask

from app.dash_apps.main_dash import (
    build_asset_figure,
    build_asset_y_slider_state,
    build_overview_layout,
    parse_compare_symbols_from_search,
    parse_symbol_from_pathname,
)
from app.index_config import INDEX_COLOR_CONFIG, get_tracked_assets


def _collect_component_ids(component) -> set[str]:
    if component is None:
        return set()

    component_ids: set[str] = set()
    component_id = getattr(component, "id", None)
    if isinstance(component_id, str) and component_id:
        component_ids.add(component_id)

    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            component_ids.update(_collect_component_ids(child))
    elif children is not None:
        component_ids.update(_collect_component_ids(children))
    return component_ids


def _find_component_by_id(component, target_id):
    if component is None:
        return None
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            found = _find_component_by_id(child, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_component_by_id(children, target_id)
    return None


def test_parse_symbol_from_pathname_returns_symbol_for_detail_route():
    assert parse_symbol_from_pathname("/dash/assets/SXR8.DE") == "SXR8.DE"


def test_parse_symbol_from_pathname_returns_none_for_non_detail_route():
    assert parse_symbol_from_pathname("/dash/") is None
    assert parse_symbol_from_pathname("/stocks/SXR8.DE") is None


def test_parse_compare_symbols_from_search_returns_symbols():
    left, right = parse_compare_symbols_from_search("?left=SXR8.DE&right=EXSA.DE")

    assert left == "SXR8.DE"
    assert right == "EXSA.DE"


def test_build_overview_layout_includes_choropleth_controls():
    app = Flask(__name__)
    app.config["TRACKED_ASSETS"] = []

    with app.app_context():
        layout = build_overview_layout()

    component_ids = _collect_component_ids(layout)
    assert {"world-map", "overview-index-dropdown", "overview-metric-dropdown", "world-map-status"}.issubset(component_ids)


def test_build_overview_layout_color_cards_use_shared_config():
    app = Flask(__name__)
    app.config["TRACKED_ASSETS"] = get_tracked_assets()

    with app.app_context():
        layout = build_overview_layout()

    asset_grid = None
    for child in getattr(layout.children[1], "children", []):
        if getattr(child, "className", None) == "asset-grid":
            asset_grid = child
            break
    assert asset_grid is not None
    first_link = asset_grid.children[0]
    first_card = first_link.children
    style = first_card.style
    assert style["--etf-color-base"] == INDEX_COLOR_CONFIG["gold"]["base_color"]
    assert style["--etf-color-light"] == INDEX_COLOR_CONFIG["gold"]["light_color"]
    assert style["--etf-color-dark"] == INDEX_COLOR_CONFIG["gold"]["dark_color"]


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
