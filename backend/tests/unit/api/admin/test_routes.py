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
