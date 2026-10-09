"""Construct application services with request-scoped infrastructure."""

from flask import current_app

from app.application.auth.service import AuthService
from app.application.events.service import EventService
from app.application.health.service import HealthService
from app.application.sessions.service import SessionService
from app.extensions import db
from app.infrastructure.health.repository import HealthRepository
from app.infrastructure.repositories.sqlalchemy_event_repository import (
    SQLAlchemyEventRepository,
)
from app.infrastructure.repositories.sqlalchemy_session_repository import (
    SQLAlchemySessionRepository,
)
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


def get_event_service() -> EventService:
    """Build the event application service with the current database session."""
    return EventService(event_repository=SQLAlchemyEventRepository(session=db.session))


def get_session_service() -> SessionService:
    """Build session management with the current database session."""
    return SessionService(
        session_repository=SQLAlchemySessionRepository(session=db.session)
    )
