from html import escape

import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.io as pio
except ModuleNotFoundError:  # pragma: no cover - optional in bare test environments
    px = None
    go = None
    pio = None

from app.services.stats_service import calculate_log2_regression

INDEX_COLOR_CONFIG = {
    "sp500": {
        "label": "S&P 500",
        "base_color": "#2563eb",
        "colorscale": [[0.0, "#dbeafe"], [1.0, "#1d4ed8"]],
    },
    "msci_canada": {
        "label": "MSCI Canada",
        "base_color": "#dc2626",
        "colorscale": [[0.0, "#fee2e2"], [1.0, "#b91c1c"]],
    },
    "msci_japan": {
        "label": "MSCI Japan",
        "base_color": "#7c3aed",
        "colorscale": [[0.0, "#ede9fe"], [1.0, "#5b21b6"]],
    },
    "stoxx_europe_600": {
        "label": "STOXX Europe 600",
        "base_color": "#16a34a",
        "colorscale": [[0.0, "#dcfce7"], [1.0, "#15803d"]],
    },
}
DEFAULT_MAP_METRIC = "company_count"
VALID_MAP_METRICS = {"company_count", "security_count", "total_weight_pct"}


def _fallback_html(title: str, message: str = "Plotly is not installed in the current environment.") -> str:
    return f"<section><h2>{escape(title)}</h2><p>{escape(message)}</p></section>"


def _empty_chart(title: str) -> str:
    if go is None:
        return _fallback_html(title)
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", height=360)
    return figure.to_html(full_html=False, include_plotlyjs=False)


def _to_html(figure: go.Figure) -> str:
    if go is None or pio is None:
        return _fallback_html("Chart")
    figure.update_layout(template="plotly_white", height=360, margin={"l": 50, "r": 20, "t": 50, "b": 40})
    return figure.to_html(full_html=False, include_plotlyjs=False)


def _empty_map_figure(title: str, annotation: str):
    if go is None:
        return {"data": [], "layout": {"title": title}}
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        height=520,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        geo={
            "projection_type": "natural earth",
            "showland": True,
            "showcountries": True,
            "showcoastlines": True,
            "landcolor": "#f8fafc",
            "countrycolor": "#cbd5e1",
            "coastlinecolor": "#94a3b8",
            "bgcolor": "#f8fafc",
        },
        annotations=[
            {
                "text": annotation,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": "#475569"},
            }
        ],
    )
    return figure


def _sanitize_country_counts(country_counts_df: pd.DataFrame, color_metric: str) -> tuple[pd.DataFrame, str]:
    working = country_counts_df.copy()
    if "iso_alpha3" not in working.columns:
        raise ValueError("country_counts_df is missing required column: iso_alpha3")

    metric = color_metric if color_metric in working.columns and color_metric in VALID_MAP_METRICS else DEFAULT_MAP_METRIC
    required_columns = {
        "index_id",
        "index_name",
        "country",
        "iso_alpha3",
        "tax_residence_country",
        "tax_residence_iso_alpha3",
        "company_count",
        "security_count",
        "total_weight_pct",
        "tax_country_basis",
        "tax_country_confidence",
    }
    missing_columns = sorted(required_columns.difference(working.columns))
    if missing_columns:
        raise ValueError(f"country_counts_df is missing required columns: {', '.join(missing_columns)}")

    working["iso_alpha3"] = working["iso_alpha3"].fillna("").astype(str).str.strip().str.upper()
    working = working[working["iso_alpha3"] != ""].copy()
    for numeric_column in ["company_count", "security_count", "total_weight_pct", metric]:
        if numeric_column in working.columns:
            working[numeric_column] = pd.to_numeric(working[numeric_column], errors="coerce")
    working = working.dropna(subset=[metric])
    return working, metric


def _hover_template() -> str:
    return (
        "<b>%{customdata[0]}</b><br>"
        "Country=%{customdata[1]}<br>"
        "ISO-3=%{location}<br>"
        "Company count=%{customdata[2]}<br>"
        "Security count=%{customdata[3]}<br>"
        "Total weight %%=%{customdata[4]:.2f}<br>"
        "Tax-country basis=%{customdata[5]}<br>"
        "Tax-country confidence=%{customdata[6]}<extra></extra>"
    )


def _build_single_index_trace(index_df: pd.DataFrame, index_id: str, color_metric: str, showscale: bool = True):
    color_config = INDEX_COLOR_CONFIG.get(index_id, {
        "label": index_df["index_name"].iloc[0] if not index_df.empty else index_id,
        "base_color": "#475569",
        "colorscale": [[0.0, "#e2e8f0"], [1.0, "#475569"]],
    })
    z_values = pd.to_numeric(index_df[color_metric], errors="coerce").fillna(0)
    colorbar_title = {
        "company_count": "Company count",
        "security_count": "Security count",
        "total_weight_pct": "Total weight %",
    }.get(color_metric, color_metric.replace("_", " ").title())
    return go.Choropleth(
        locations=index_df["iso_alpha3"],
        locationmode="ISO-3",
        z=z_values,
        text=index_df["country"],
        name=color_config["label"],
        colorscale=color_config["colorscale"],
        marker_line_color="#ffffff",
        marker_line_width=0.6,
        hovertemplate=_hover_template(),
        customdata=index_df[[
            "index_name",
            "country",
            "company_count",
            "security_count",
            "total_weight_pct",
            "tax_country_basis",
            "tax_country_confidence",
        ]].to_numpy(),
        colorbar_title=colorbar_title,
        showscale=showscale,
    )


def build_etf_country_exposure_map(
    country_counts_df: pd.DataFrame,
    selected_index_id: str | None = None,
    color_metric: str = "company_count",
):
    if px is None or go is None:
        raise RuntimeError("Plotly is not installed in the current environment.")

    sanitized_df, metric = _sanitize_country_counts(country_counts_df, color_metric)
    if sanitized_df.empty:
        return _empty_map_figure("Company exposure by country", "No country exposure data is available.")

    available_index_ids = [index_id for index_id in sanitized_df["index_id"].dropna().astype(str).unique().tolist() if index_id]
    if selected_index_id and selected_index_id != "all":
        selected_id = str(selected_index_id).strip().lower()
        filtered_df = sanitized_df[sanitized_df["index_id"].astype(str).str.lower() == selected_id].copy()
        if filtered_df.empty:
            return _empty_map_figure("Company exposure by country", f"No country exposure data is available for '{selected_index_id}'.")

        index_name = filtered_df["index_name"].iloc[0]
        figure = go.Figure(data=[_build_single_index_trace(filtered_df, selected_id, metric, showscale=True)])
        figure.update_layout(
            title=f"{index_name} company exposure by country",
            template="plotly_white",
            height=520,
            margin={"l": 10, "r": 10, "t": 60, "b": 10},
            geo={
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
            },
        )
        return figure

    figure = go.Figure()
    # Overview mode overlays one choropleth trace per index. Countries that appear in multiple
    # indices can visually blend, so the dashboard should default to a single selected index.
    for index_id in available_index_ids:
        index_df = sanitized_df[sanitized_df["index_id"].astype(str).str.lower() == index_id].copy()
        if index_df.empty:
            continue
        trace = _build_single_index_trace(index_df, index_id, metric, showscale=False)
        figure.add_trace(trace)

    if not figure.data:
        return _empty_map_figure("Company exposure by country", "No country exposure data is available.")

    figure.update_layout(
        title="Company exposure by country",
        template="plotly_white",
        height=520,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        geo={
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
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    return figure


def build_index_country_choropleth(country_counts_df: pd.DataFrame, color_column: str = "company_count"):
    selected_index_id = None
    if "index_id" in country_counts_df.columns:
        unique_ids = [value for value in country_counts_df["index_id"].dropna().astype(str).unique().tolist() if value]
        if len(unique_ids) == 1:
            selected_index_id = unique_ids[0]
    return build_etf_country_exposure_map(country_counts_df, selected_index_id=selected_index_id, color_metric=color_column)


def price_chart(frame: pd.DataFrame, symbol: str) -> str:
    if frame.empty or "analysis_price" not in frame:
        return _empty_chart("Long-Term Price")
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["date"], y=frame["analysis_price"], mode="lines", name="Price"))
    if "price_trend" in frame:
        figure.add_trace(go.Scatter(x=frame["date"], y=frame["price_trend"], mode="lines", name="Regression trend"))
    figure.update_layout(title=f"{symbol} Long-Term Price With Trend", xaxis_title="Date", yaxis_title="Price")
    return _to_html(figure)


def volume_chart(frame: pd.DataFrame, symbol: str) -> str:
    if frame.empty:
        return _empty_chart("Volume")
    figure = go.Figure()
    figure.add_trace(go.Bar(x=frame["date"], y=frame["volume"], name="Volume"))
    figure.update_layout(title=f"{symbol} Volume", xaxis_title="Date", yaxis_title="Volume")
    return _to_html(figure)


def log2_price_chart(frame: pd.DataFrame, symbol: str) -> str:
    if frame.empty or "log2_price" not in frame:
        return _empty_chart("Log2 Price")
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["date"], y=frame["log2_price"], mode="lines", name="Log2 price"))
    if "log2_trend" in frame:
        figure.add_trace(go.Scatter(x=frame["date"], y=frame["log2_trend"], mode="lines", name="Regression line"))
    figure.update_layout(title=f"{symbol} Log2 Price With Regression", xaxis_title="Date", yaxis_title="Log2 price")
    return _to_html(figure)


def deviation_chart(frame: pd.DataFrame, symbol: str) -> str:
    if frame.empty or "log2_deviation" not in frame:
        return _empty_chart("Deviation")
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["date"], y=frame["log2_deviation"], mode="lines", name="Log2 residual"))
    figure.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    figure.update_layout(title=f"{symbol} Residual From Log2 Trend", xaxis_title="Date", yaxis_title="Log2 residual")
    return _to_html(figure)


def create_price_chart_with_log2_regression(
    df: pd.DataFrame,
    symbol: str,
    name: str | None = None,
    price_column: str = "Adj Close",
) -> str:
    title = f"{name or symbol}: Kursverlauf mit Log2-Regression"
    if df.empty:
        return _empty_chart(title)

    chart_frame = df.copy()
    selected_price_column = price_column if price_column in chart_frame.columns else "Close"
    if "Log2 Regression" not in chart_frame.columns:
        chart_frame, metadata = calculate_log2_regression(chart_frame, price_column=selected_price_column)
        selected_price_column = str(metadata["price_column"])

    if go is None or pio is None:
        return _fallback_html(title)

    x_axis = chart_frame["Date"] if "Date" in chart_frame.columns else chart_frame.index
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=x_axis,
            y=chart_frame[selected_price_column],
            mode="lines",
            name="Realer Kurs",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_axis,
            y=chart_frame["Log2 Regression"],
            mode="lines",
            name="Log2 Regression",
        )
    )
    figure.update_layout(
        title=title,
        template="plotly_white",
        height=420,
        margin={"l": 50, "r": 20, "t": 60, "b": 50},
        xaxis_title="Datum",
        yaxis_title="Preis",
    )
    return pio.to_html(figure, full_html=False, include_plotlyjs=False)
