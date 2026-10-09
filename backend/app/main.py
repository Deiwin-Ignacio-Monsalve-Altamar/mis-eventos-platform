"""Create and configure the Flask application and its API routes."""

from flask import Flask

from app.api.auth.routes import auth_bp
from app.api.events.routes import event_bp
from app.api.health.routes import health_bp
from app.config import Config
from app.extensions import db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(event_bp, url_prefix="/api/v1")

    return app
