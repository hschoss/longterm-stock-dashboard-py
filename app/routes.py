from flask import Blueprint, abort, current_app, flash, redirect, render_template


from app.services.data_service import (
    download_price_data,
    get_asset_by_symbol,
    store_price_data_in_database,
)


bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return redirect("/dash/")


@bp.get("/stocks")
def stocks():
    return render_template("stocks.html", assets=current_app.config.get("TRACKED_ASSETS", []))


@bp.get("/stocks/<symbol>")
def stock_detail(symbol: str):
    asset = get_asset_by_symbol(symbol)
    if asset is None:
        abort(404)
    return redirect(f"/dash/assets/{asset['symbol']}")


@bp.get("/dash/assets/<symbol>")
def dash_asset_entry(symbol: str):
    dash_app = current_app.extensions.get("main_dash_app")
    if dash_app is None:
        abort(404)
    return dash_app.index()


@bp.get("/dash/compare")
@bp.get("/dash/compare/")
def dash_compare_entry():
    dash_app = current_app.extensions.get("main_dash_app")
    if dash_app is None:
        abort(404)
    return dash_app.index()


@bp.get("/stocks/<symbol>/refresh")
def refresh_stock(symbol: str):
    asset = get_asset_by_symbol(symbol)
    if asset is None:
        abort(404)

    
    try:
        frame = download_price_data(asset["symbol"], overwrite=True)
        imported_count = store_price_data_in_database(asset["symbol"], frame)
    
        flash(
            f"{imported_count} Kurszeilen für {asset['name']} wurden aktualisiert "
            "und in PostgreSQL gespeichert.",
            "success",
        )
    except Exception as exc:
        flash(
            f"Kursdaten für {asset['name']} konnten nicht aktualisiert werden: {exc}",
            "error",
        )

    return redirect(f"/dash/assets/{asset['symbol']}")
