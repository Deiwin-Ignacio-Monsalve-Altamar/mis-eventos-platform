from flask import current_app

from app.application.auth.service import AuthService
from app.application.health.service import HealthService
from app.extensions import db
from app.infrastructure.health.repository import HealthRepository
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)


def get_health_service() -> HealthService:
    health_repository = HealthRepository()

    return HealthService(health_port=health_repository)


def get_auth_service() -> AuthService:
    """Build the authentication service with request-scoped dependencies."""
    user_repository = SQLAlchemyUserRepository(session=db.session)
    return AuthService(
        user_repository=user_repository,
        jwt_secret=current_app.config.get("JWT_SECRET_KEY"),
        access_token_ttl_seconds=current_app.config["JWT_ACCESS_TOKEN_TTL_SECONDS"],
    )
