from flask import Flask

from app.api.health.routes import health_bp
from app.config import Config
from app.extensions import db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api/v1")

    return app
