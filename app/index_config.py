from __future__ import annotations

from copy import deepcopy

INDEX_COLOR_CONFIG = {
    "gold": {
        "label": "Gold",
        "base_color": "#ca8a04",
        "light_color": "#fef3c7",
        "dark_color": "#a16207",
        "colorscale": [[0.0, "#fef3c7"], [1.0, "#a16207"]],
        "map_enabled": False,
    },
    "emerging_markets": {
        "label": "MSCI Emerging Markets",
        "base_color": "#0891b2",
        "light_color": "#cffafe",
        "dark_color": "#0e7490",
        "colorscale": [[0.0, "#cffafe"], [1.0, "#0e7490"]],
        "map_enabled": True,
    },
    "sp500": {
        "label": "S&P 500",
        "base_color": "#2563eb",
        "light_color": "#dbeafe",
        "dark_color": "#1d4ed8",
        "colorscale": [[0.0, "#dbeafe"], [1.0, "#1d4ed8"]],
        "map_enabled": True,
    },
    "msci_japan": {
        "label": "MSCI Japan",
        "base_color": "#7c3aed",
        "light_color": "#ede9fe",
        "dark_color": "#5b21b6",
        "colorscale": [[0.0, "#ede9fe"], [1.0, "#5b21b6"]],
        "map_enabled": True,
    },
    "msci_pacific_ex_japan": {
        "label": "MSCI Pacific ex-Japan",
        "base_color": "#0f766e",
        "light_color": "#ccfbf1",
        "dark_color": "#115e59",
        "colorscale": [[0.0, "#ccfbf1"], [1.0, "#115e59"]],
        "map_enabled": False,
    },
    "stoxx_europe_600": {
        "label": "STOXX Europe 600",
        "base_color": "#16a34a",
        "light_color": "#dcfce7",
        "dark_color": "#15803d",
        "colorscale": [[0.0, "#dcfce7"], [1.0, "#15803d"]],
        "map_enabled": True,
    },
    "msci_canada": {
        "label": "MSCI Canada",
        "base_color": "#dc2626",
        "light_color": "#fee2e2",
        "dark_color": "#b91c1c",
        "colorscale": [[0.0, "#fee2e2"], [1.0, "#b91c1c"]],
        "map_enabled": True,
    },
}

INDEX_DISPLAY_ORDER = [
    "gold",
    "emerging_markets",
    "sp500",
    "msci_japan",
    "msci_pacific_ex_japan",
    "stoxx_europe_600",
    "msci_canada",
]

TRACKED_ASSETS = [
    {
        "asset_id": "gold",
        "index_id": "gold",
        "name": "Gold price",
        "symbol": "GOLD",
        "wkn": "A0Q2XG",
        "isin": "XC0009655157",
        "index": "Gold",
        "provider": "Commodity",
        "distribution": "n/a",
        "map_label": "Global",
        "lat": None,
        "lon": None,
        "region": "Global",
        "asset_kind": "commodity",
        "map_enabled": False,
        "card_note": "Commodity price asset. No company-country constituent map.",
    },
    {
        "asset_id": "emerging_markets",
        "index_id": "emerging_markets",
        "name": "Xtrackers MSCI Emerging Markets UCITS ETF 1C",
        "symbol": "XMME.DE",
        "wkn": "A12GVR",
        "isin": "IE00BTJRMP35",
        "index": "MSCI Emerging Markets",
        "provider": "Xtrackers",
        "distribution": "acc",
        "map_label": "Emerging Markets",
        "lat": 20.0,
        "lon": 80.0,
        "region": "Global Emerging Markets",
        "asset_kind": "etf",
        "map_enabled": True,
        "card_note": "Broad emerging markets equity exposure.",
    },
    {
        "asset_id": "sp500",
        "index_id": "sp500",
        "name": "iShares Core S&P 500 UCITS ETF USD (Acc)",
        "symbol": "SXR8.DE",
        "wkn": "A0YEDG",
        "isin": "IE00B5BMR087",
        "index": "S&P 500",
        "provider": "iShares",
        "distribution": "acc",
        "map_label": "USA",
        "lat": 39.8283,
        "lon": -98.5795,
        "region": "North America",
        "asset_kind": "etf",
        "map_enabled": True,
        "card_note": "Tracks large-cap U.S. equity exposure.",
    },
    {
        "asset_id": "msci_japan",
        "index_id": "msci_japan",
        "name": "iShares MSCI Japan UCITS ETF USD (Dist)",
        "symbol": "IQQJ.DE",
        "alternative_symbol": "IJPN.L",
        "wkn": "A0DK60",
        "isin": "IE00B02KXH56",
        "index": "MSCI Japan",
        "provider": "iShares",
        "distribution": "dist",
        "map_label": "Japan",
        "lat": 36.2048,
        "lon": 138.2529,
        "region": "Asia",
        "asset_kind": "etf",
        "map_enabled": True,
        "card_note": "Tracks Japanese equity exposure.",
    },
    {
        "asset_id": "msci_pacific_ex_japan",
        "index_id": "msci_pacific_ex_japan",
        "name": "iShares MSCI Pacific ex-Japan UCITS ETF USD",
        "symbol": "IPXJ.L",
        "wkn": "",
        "isin": "",
        "index": "MSCI Pacific ex-Japan",
        "provider": "iShares",
        "distribution": "",
        "map_label": "Pacific ex-Japan",
        "lat": -25.2744,
        "lon": 133.7751,
        "region": "Asia-Pacific",
        "asset_kind": "etf",
        "map_enabled": False,
        "card_note": "Tracks developed Pacific equity exposure excluding Japan.",
    },
    {
        "asset_id": "stoxx_europe_600",
        "index_id": "stoxx_europe_600",
        "name": "iShares STOXX Europe 600 UCITS ETF (DE)",
        "symbol": "EXSA.DE",
        "wkn": "263530",
        "isin": "DE0002635307",
        "index": "STOXX Europe 600",
        "provider": "iShares",
        "distribution": "dist",
        "map_label": "Europe",
        "lat": 50.1109,
        "lon": 8.6821,
        "region": "Europe",
        "asset_kind": "etf",
        "map_enabled": True,
        "card_note": "Tracks large- and mid-cap European equities.",
    },
    {
        "asset_id": "msci_canada",
        "index_id": "msci_canada",
        "name": "iShares MSCI Canada UCITS ETF USD (Acc)",
        "symbol": "CCAU.L",
        "wkn": "A0YEDS",
        "isin": "IE00B52SF786",
        "index": "MSCI Canada",
        "provider": "iShares",
        "distribution": "acc",
        "map_label": "Canada",
        "lat": 56.1304,
        "lon": -106.3468,
        "region": "North America",
        "asset_kind": "etf",
        "map_enabled": True,
        "card_note": "Tracks Canadian equity exposure.",
    },
]

MAP_ENABLED_INDEX_IDS = tuple(index_id for index_id in INDEX_DISPLAY_ORDER if INDEX_COLOR_CONFIG[index_id]["map_enabled"])
TRACKED_ASSET_IDS = tuple(asset["asset_id"] for asset in TRACKED_ASSETS)


def get_index_color_config(index_id: str) -> dict:
    normalized = index_id.strip().lower()
    if normalized not in INDEX_COLOR_CONFIG:
        raise KeyError(f"Unknown index color config for '{index_id}'.")
    return deepcopy(INDEX_COLOR_CONFIG[normalized])


def get_index_label(index_id: str, fallback: str | None = None) -> str:
    normalized = index_id.strip().lower()
    if normalized in INDEX_COLOR_CONFIG:
        return str(INDEX_COLOR_CONFIG[normalized]["label"])
    return fallback or normalized


def get_tracked_assets() -> list[dict]:
    return deepcopy(TRACKED_ASSETS)


def get_asset_map_color_style(index_id: str) -> dict[str, str]:
    config = get_index_color_config(index_id)
    return {
        "--etf-color-base": str(config["base_color"]),
        "--etf-color-light": str(config["light_color"]),
        "--etf-color-dark": str(config["dark_color"]),
    }
