"""Verify role promotion API behavior with authentication and services mocked."""

from dataclasses import replace
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.admin import routes
from app.api.admin.routes import admin_bp
from app.api.auth import decorators
from app.core.exceptions import NotFoundError, RoleConflictError, ValidationError
from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_role import UserRole

ADMIN = UserAccount(
    email="admin@example.test",
    password_hash="hash",
    first_name="Ada",
    last_name="Admin",
    id=1,
    role=UserRole.ADMIN,
)
ORGANIZER = UserAccount(
    email="organizer@example.test",
    password_hash="hash",
    first_name="Alex",
    last_name="Organizer",
    id=2,
    role=UserRole.ORGANIZER,
)


@pytest.fixture
def admin_client(monkeypatch):
    """Build the role endpoint with no database or external service."""
    app = Flask(__name__)
    service = Mock()
    service.promote_to_organizer.return_value = ORGANIZER
    auth = Mock()
    auth.get_authenticated_user.return_value = ADMIN
    monkeypatch.setattr(routes, "get_administration_service", lambda: service)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth)
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    client = app.test_client()
    client.set_cookie("access_token", "unit-test-token")
    return client, service, auth


def test_admin_promotes_attendee_and_ignores_requested_role(admin_client):
    """Return the target role and never accept a caller-supplied role value."""
    client, service, _ = admin_client

    response = client.post(
        "/api/v1/admin/users/2/promote-organizer", json={"role": "ADMIN"}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json["user"]["role"] == "ORGANIZER"
    service.promote_to_organizer.assert_called_once_with(
        2, actor_id=ADMIN.id, actor_role=UserRole.ADMIN
    )


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (UserRole.ATTENDEE, HTTPStatus.FORBIDDEN),
        (UserRole.ORGANIZER, HTTPStatus.FORBIDDEN),
    ],
)
def test_non_admin_cannot_promote_users(admin_client, role, status):
    """Reject attendee and organizer requests before invoking the promotion use case."""
    client, service, auth = admin_client
    auth.get_authenticated_user.return_value = replace(ADMIN, role=role)

    response = client.post("/api/v1/admin/users/2/promote-organizer")

    assert response.status_code == status
    service.promote_to_organizer.assert_not_called()


def test_promotion_maps_missing_target_and_invalid_self_promotion(admin_client):
    """Return established not-found and validation responses for invalid targets."""
    client, service, _ = admin_client
    service.promote_to_organizer.side_effect = NotFoundError("User not found.")

    missing = client.post("/api/v1/admin/users/99/promote-organizer")
    service.promote_to_organizer.side_effect = ValidationError(
        "Users cannot promote their own account."
    )
    self_promotion = client.post("/api/v1/admin/users/1/promote-organizer")

    assert missing.status_code == HTTPStatus.NOT_FOUND
    assert self_promotion.status_code == HTTPStatus.BAD_REQUEST


def test_promotion_maps_already_admin_target_to_conflict(admin_client):
    """Do not allow the organizer-promotion operation to assign administrator."""
    client, service, _ = admin_client
    service.promote_to_organizer.side_effect = RoleConflictError(
        "Administrators cannot be promoted to organizer."
    )

    response = client.post("/api/v1/admin/users/3/promote-organizer")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json["error"]["code"] == "role_conflict"


def test_admin_can_list_users_with_pagination_and_search(admin_client):
    """Expose only requested directory results and their pagination metadata."""
    from app.application.dto.user_page import UserPage
    from app.domain.entities.user_summary import UserSummary

    client, service, _ = admin_client
    summary = UserSummary(8, "person@example.test", "Pat", "Example", UserRole.ATTENDEE)
    service.list_users.return_value = UserPage((summary,), 2, 10, 11)

    response = client.get("/api/v1/admin/users?page=2&page_size=10&q=Pat")

    assert response.status_code == HTTPStatus.OK
    assert response.json == {
        "users": [
            {
                "id": 8,
                "email": "person@example.test",
                "first_name": "Pat",
                "last_name": "Example",
                "role": "ATTENDEE",
            }
        ],
        "pagination": {"page": 2, "page_size": 10, "total": 11, "total_pages": 2},
    }
    service.list_users.assert_called_once_with("2", "10", "Pat")


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (UserRole.ATTENDEE, HTTPStatus.FORBIDDEN),
        (UserRole.ORGANIZER, HTTPStatus.FORBIDDEN),
    ],
)
def test_non_admin_cannot_list_users(admin_client, role, expected_status):
    """Restrict directory access to administrators before service invocation."""
    client, service, auth = admin_client
    auth.get_authenticated_user.return_value = replace(ADMIN, role=role)

    response = client.get("/api/v1/admin/users")

    assert response.status_code == expected_status
    service.list_users.assert_not_called()


def test_user_list_maps_invalid_pagination_to_bad_request(admin_client):
    """Keep malformed directory filters within the established API error shape."""
    client, service, _ = admin_client
    service.list_users.side_effect = ValidationError("page must be a positive integer.")

    response = client.get("/api/v1/admin/users?page=0")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json["error"]["code"] == "invalid_request"


def test_anonymous_user_cannot_list_users(admin_client):
    """Require the existing authenticated cookie before role checking."""
    client, service, _ = admin_client
    client.delete_cookie("access_token")

    response = client.get("/api/v1/admin/users")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    service.list_users.assert_not_called()


def test_admin_dashboard_returns_aggregate_service_data(admin_client, monkeypatch):
    """Expose dashboard aggregates only through the admin route group."""
    from app.api.admin import routes

    client, _, _ = admin_client
    analytics = Mock()
    analytics.dashboard.return_value = {"summary": {"users": {"total": 4}}}
    monkeypatch.setattr(routes, "get_admin_analytics_service", lambda: analytics)

    response = client.get("/api/v1/admin/dashboard")

    assert response.status_code == HTTPStatus.OK
    assert response.json == {"dashboard": {"summary": {"users": {"total": 4}}}}


@pytest.mark.parametrize("role", [UserRole.ATTENDEE, UserRole.ORGANIZER])
def test_non_admin_cannot_access_admin_dashboard(admin_client, monkeypatch, role):
    """Keep aggregate platform metrics behind the authoritative role decorator."""
    client, _, auth = admin_client
    auth.get_authenticated_user.return_value = replace(ADMIN, role=role)
    analytics = Mock()
    monkeypatch.setattr(routes, "get_admin_analytics_service", lambda: analytics)

    response = client.get("/api/v1/admin/dashboard")

    assert response.status_code == HTTPStatus.FORBIDDEN
    analytics.dashboard.assert_not_called()


def test_anonymous_user_cannot_access_admin_dashboard(admin_client, monkeypatch):
    """Require a valid authentication cookie before querying global metrics."""
    client, _, _ = admin_client
    analytics = Mock()
    monkeypatch.setattr(routes, "get_admin_analytics_service", lambda: analytics)
    client.delete_cookie("access_token")

    response = client.get("/api/v1/admin/dashboard")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    analytics.dashboard.assert_not_called()
