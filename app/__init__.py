from flask import Flask

from app.config import Config


def create_app(config_object: type[Config] = Config) -> Flask:
    from app.dash_apps.main_dash import register_main_dash_app
    from app.extensions import close_db, init_db
    from app.routes import bp

    app = Flask(__name__)
    app.config.from_object(config_object)

    init_db(app)
    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)
    register_main_dash_app(app)

    return app
