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

def build_index_country_choropleth(country_counts_df: pd.DataFrame, color_column: str = "company_count"):
    required_columns = {
        "country",
        "iso_alpha3",
        "index_name",
        "company_count",
        "security_count",
        "total_weight_pct",
    }
    missing_columns = sorted(required_columns.difference(country_counts_df.columns))
    if missing_columns:
        raise ValueError(f"country_counts_df is missing required columns: {', '.join(missing_columns)}")
    if color_column not in country_counts_df.columns:
        raise ValueError(f"color column '{color_column}' is not present in country_counts_df")
    if px is None or go is None:
        raise RuntimeError("Plotly is not installed in the current environment.")

    if country_counts_df.empty:
        figure = go.Figure()
        figure.update_layout(
            title="Index Country Composition",
            template="plotly_white",
            margin={"l": 20, "r": 20, "t": 60, "b": 20},
        )
        return figure

    figure = px.choropleth(
        country_counts_df,
        locations="iso_alpha3",
        color=color_column,
        hover_name="country",
        hover_data={
            "index_name": True,
            "company_count": True,
            "security_count": True,
            "total_weight_pct": ":.2f",
            "iso_alpha3": False,
        },
        projection="natural earth",
    )
    figure.update_geos(showcoastlines=True, showframe=False)
    figure.update_layout(
        template="plotly_white",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        coloraxis_colorbar_title=color_column.replace("_", " ").title(),
    )
    return figure

