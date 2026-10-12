"""Construct application services with request-scoped infrastructure."""

from flask import current_app

from app.application.administration.analytics_service import AdminAnalyticsService
from app.application.administration.service import AdministrationService
from app.application.auth.service import AuthService
from app.application.events.image_service import EventImageService
from app.application.events.service import EventService
from app.application.health.service import HealthService
from app.application.registrations.service import EventRegistrationService
from app.application.sessions.attendees import SessionAttendeeService
from app.application.sessions.service import SessionService
from app.extensions import db
from app.infrastructure.health.repository import HealthRepository
from app.infrastructure.repositories.sqlalchemy_admin_analytics_repository import (
    SQLAlchemyAdminAnalyticsRepository,
)
from app.infrastructure.repositories.sqlalchemy_event_image_repository import (
    SQLAlchemyEventImageRepository,
)
from app.infrastructure.repositories.sqlalchemy_event_registration_repository import (
    SQLAlchemyEventRegistrationRepository,
)
from app.infrastructure.repositories.sqlalchemy_event_repository import (
    SQLAlchemyEventRepository,
)
from app.infrastructure.repositories.sqlalchemy_session_attendee_repository import (
    SQLAlchemySessionAttendeeRepository,
)
from app.infrastructure.repositories.sqlalchemy_session_repository import (
    SQLAlchemySessionRepository,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.storage.cloudinary_storage import create_cloudinary_storage


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


def get_administration_service() -> AdministrationService:
    """Build role-administration use cases from the active database session."""
    return AdministrationService(user_repository=SQLAlchemyUserRepository(db.session))


def get_admin_analytics_service() -> AdminAnalyticsService:
    """Build platform analytics using request-scoped aggregate persistence."""
    return AdminAnalyticsService(SQLAlchemyAdminAnalyticsRepository(db.session))


def get_event_service() -> EventService:
    """Build the event application service with the current database session."""
    image_service = EventImageService(
        repository=SQLAlchemyEventImageRepository(session=db.session),
        client_factory=lambda: create_cloudinary_storage(current_app.config),
    )
    return EventService(
        event_repository=SQLAlchemyEventRepository(session=db.session),
        event_image_service=image_service,
    )


def get_session_service() -> SessionService:
    """Build session management with the current database session."""
    return SessionService(
        session_repository=SQLAlchemySessionRepository(session=db.session)
    )


def get_session_attendee_service() -> SessionAttendeeService:
    """Build session attendee operations with the current database session."""
    return SessionAttendeeService(
        repository=SQLAlchemySessionAttendeeRepository(session=db.session)
    )


def get_event_registration_service() -> EventRegistrationService:
    """Build event registration use cases with the active database session."""
    return EventRegistrationService(
        repository=SQLAlchemyEventRegistrationRepository(session=db.session)
    )
