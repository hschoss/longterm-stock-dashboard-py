"""Weltkarte der Laender-Exposure je Index (migriert aus dem alten
app/charts/plotly_charts.py:build_etf_country_exposure_map). Liest ueber
storage.repositories.index_constituents; solange die Datenquelle CSV ist, bleibt die
Migration nach ref.index_country_exposure ein offener Punkt aus docs/plan.md."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from findash.app.figures._common import apply_mobile_layout, empty_figure

VALID_MAP_METRICS = {"company_count", "security_count", "total_weight_pct"}
DEFAULT_MAP_METRIC = "company_count"

_GEO_LAYOUT = {
    "projection_type": "natural earth",
    "showland": True,
    "showcountries": True,
    "showcoastlines": True,
    "landcolor": "#f8fafc",
    "countrycolor": "#cbd5e1",
    "coastlinecolor": "#94a3b8",
    "showocean": True,
    "oceancolor": "#eff6ff",
    "bgcolor": "#f8fafc",
}


def _sanitize(country_counts: pd.DataFrame, color_metric: str) -> tuple[pd.DataFrame, str]:
    if "iso_alpha3" not in country_counts.columns:
        raise ValueError("country_counts braucht die Spalte iso_alpha3.")

    metric = color_metric if color_metric in VALID_MAP_METRICS else DEFAULT_MAP_METRIC
    working = country_counts.copy()
    working["iso_alpha3"] = working["iso_alpha3"].fillna("").astype(str).str.strip().str.upper()
    working = working[working["iso_alpha3"] != ""].copy()
    working[metric] = pd.to_numeric(working[metric], errors="coerce")
    return working.dropna(subset=[metric]), metric


def _color_scale(base_color: str | None) -> list[list[object]]:
    return [[0.0, "#f1f5f9"], [1.0, base_color or "#475569"]]


def _trace(index_df: pd.DataFrame, label: str, color: str | None, metric: str, showscale: bool) -> go.Choropleth:
    return go.Choropleth(
        locations=index_df["iso_alpha3"],
        locationmode="ISO-3",
        z=pd.to_numeric(index_df[metric], errors="coerce").fillna(0),
        text=index_df.get("country", ""),
        name=label,
        colorscale=_color_scale(color),
        marker_line_color="#ffffff",
        marker_line_width=0.6,
        hovertemplate=(
            f"<b>{label}</b><br>Country=%{{text}}<br>ISO-3=%{{location}}<br>"
            f"{metric.replace('_', ' ').title()}=%{{z}}<extra></extra>"
        ),
        colorbar_title=metric.replace("_", " ").title(),
        showscale=showscale,
    )


def build_country_exposure_figure(
    country_counts: pd.DataFrame,
    selected_index_key: str | None,
    color_metric: str = DEFAULT_MAP_METRIC,
    index_labels: dict[str, str] | None = None,
    index_colors: dict[str, str] | None = None,
) -> go.Figure:
    """country_counts braucht mindestens die Spalten index_id, iso_alpha3 und die
    gewaehlte Metrik. selected_index_key=None zeichnet alle Indizes uebereinander."""

    try:
        sanitized, metric = _sanitize(country_counts, color_metric)
    except ValueError as exc:
        return empty_figure(str(exc))

    if sanitized.empty:
        return empty_figure("Keine Laenderdaten verfuegbar.")

    index_labels = index_labels or {}
    index_colors = index_colors or {}

    figure = go.Figure()
    if selected_index_key:
        filtered = sanitized[sanitized["index_id"].astype(str).str.lower() == selected_index_key.lower()]
        if filtered.empty:
            return empty_figure(f"Keine Laenderdaten fuer '{selected_index_key}'.")
        label = index_labels.get(selected_index_key, selected_index_key)
        figure.add_trace(_trace(filtered, label, index_colors.get(selected_index_key), metric, showscale=True))
    else:
        for index_key in sorted(sanitized["index_id"].dropna().astype(str).unique()):
            index_df = sanitized[sanitized["index_id"].astype(str) == index_key]
            label = index_labels.get(index_key, index_key)
            figure.add_trace(_trace(index_df, label, index_colors.get(index_key), metric, showscale=False))
        figure.update_layout(legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0})

    figure.update_layout(title="Laender-Exposure der Indexbestandteile", geo=_GEO_LAYOUT, height=480)
    return apply_mobile_layout(figure)
