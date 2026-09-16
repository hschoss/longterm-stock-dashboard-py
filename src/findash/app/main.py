"""Dash-Einstiegspunkt. `server` ist die Flask-App fuer gunicorn (docker/Dockerfile).
Ersetzt die alte Flask-Huelle vollstaendig (docs/plan.md Abschnitt 6: Flask-Blueprint,
Jinja-Templates und Refresh-Route entfallen)."""

from __future__ import annotations

from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import html
from dash_bootstrap_templates import load_figure_template
from flask import Response, jsonify

from findash.app.data_access import get_last_successful_sync
from findash.core.logging import configure_logging
from findash.core.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)

load_figure_template(["bootstrap"])

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=str(Path(__file__).parent / "pages"),
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    title="Findash",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server


def _navbar() -> dbc.NavbarSimple:
    links = [
        dbc.NavLink(page["name"], href=page["path"], active="exact")
        for page in dash.page_registry.values()
        if not page.get("path_template")
    ]
    return dbc.NavbarSimple(children=links, brand="Findash", brand_href="/", className="mb-3")


def _status_bar() -> dbc.Alert:
    try:
        last_sync = get_last_successful_sync()
    except Exception:  # pragma: no cover - DB evtl. noch nicht migriert/erreichbar
        last_sync = None

    sync_text = f"Letzter Sync: {last_sync:%Y-%m-%d %H:%M}" if last_sync else "Letzter Sync: kein Lauf vorhanden"
    return dbc.Alert(
        [html.Strong("Keine Anlageberatung. "), sync_text],
        color="secondary",
        className="mb-3 py-2 small",
    )


def serve_layout() -> html.Div:
    return html.Div([_navbar(), dbc.Container([_status_bar(), dash.page_container], fluid=True, className="px-3 pb-4")])


app.layout = serve_layout


@server.get("/healthz")
def healthz() -> Response:
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(debug=settings.debug, host="0.0.0.0", port=5000)
