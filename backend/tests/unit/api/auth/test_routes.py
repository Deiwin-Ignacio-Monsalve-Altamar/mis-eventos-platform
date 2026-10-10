"""Verify authentication route responses with application services mocked."""

from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.auth import routes as auth_routes
from app.api.auth.routes import auth_bp
from app.core.exceptions import (
    AuthenticationError,
    DuplicateAccountError,
    ValidationError,
)
from app.domain.entities.user_account import UserAccount

TEST_TOKEN = "test-access-token"
ACCOUNT = UserAccount(
    id=7,
    email="attendee@example.test",
    password_hash="private-password-hash",
    first_name="Alex",
    last_name="Rivera",
)


@pytest.fixture
def auth_client(monkeypatch):
    """Provide auth routes with a mocked service and no database extension."""
    return _make_auth_client(monkeypatch, secure_cookie=False)


@pytest.fixture
def secure_auth_client(monkeypatch):
    """Provide auth routes configured to mark cookies as Secure."""
    return _make_auth_client(monkeypatch, secure_cookie=True)


def _make_auth_client(monkeypatch, secure_cookie):
    """Build the authentication test client with the requested cookie policy."""
    app = Flask(__name__)
    app.config.update(
        JWT_ACCESS_TOKEN_TTL_SECONDS=3600,
        JWT_COOKIE_SECURE=secure_cookie,
    )
    service = Mock()
    service.register.return_value = ACCOUNT
    service.authenticate.return_value = (ACCOUNT, TEST_TOKEN)
    service.get_authenticated_user.return_value = ACCOUNT
    monkeypatch.setattr(auth_routes, "get_auth_service", lambda: service)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: service)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    return app.test_client(), service


def registration_payload(**overrides):
    """Build a registration request body with optional field overrides."""
    payload = {
        "email": "attendee@example.test",
        "password": "correct-horse-battery",
        "first_name": "Alex",
        "last_name": "Rivera",
    }
    payload.update(overrides)
    return payload


def test_registration_returns_public_account_and_calls_service(auth_client):
    """Return 201 and delegate registration fields to the application service."""
    client, service = auth_client

    response = client.post("/api/v1/auth/register", json=registration_payload())

    assert response.status_code == 201
    assert response.json["user"] == {
        "id": 7,
        "email": "attendee@example.test",
        "first_name": "Alex",
        "last_name": "Rivera",
    }
    assert "password_hash" not in response.json["user"]
    service.register.assert_called_once_with(
        email="attendee@example.test",
        password="correct-horse-battery",
        first_name="Alex",
        last_name="Rivera",
    )


def test_registration_rejects_non_object_json_without_calling_service(auth_client):
    """Return 400 for malformed request bodies before service invocation."""
    client, service = auth_client

    response = client.post("/api/v1/auth/register", json=["not", "an", "object"])

    assert response.status_code == 400
    service.register.assert_not_called()


def test_registration_maps_validation_and_duplicate_errors(auth_client):
    """Translate application validation and duplicate-account errors to API errors."""
    client, service = auth_client
    service.register.side_effect = ValidationError("A valid email is required.")

    invalid_response = client.post(
        "/api/v1/auth/register", json=registration_payload(email="invalid")
    )

    service.register.side_effect = DuplicateAccountError("Account already exists.")
    duplicate_response = client.post(
        "/api/v1/auth/register", json=registration_payload()
    )

    assert invalid_response.status_code == 400
    assert invalid_response.json["error"]["code"] == "validation_error"
    assert duplicate_response.status_code == 409
    assert duplicate_response.json["error"]["code"] == "account_exists"


def test_login_returns_profile_and_http_only_cookie(auth_client):
    """Return an account profile and set the configured HttpOnly token cookie."""
    client, service = auth_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "attendee@example.test", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json["user"]["email"] == "attendee@example.test"
    assert "password_hash" not in response.json["user"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "Secure" not in response.headers["Set-Cookie"]
    service.authenticate.assert_called_once_with(
        email="attendee@example.test", password="correct-password"
    )


def test_login_maps_invalid_credentials_to_unauthorized(auth_client):
    """Return 401 when the application service rejects credentials."""
    client, service = auth_client
    service.authenticate.side_effect = AuthenticationError("Invalid credentials.")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "attendee@example.test", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_credentials"


def test_current_user_rejects_missing_and_invalid_tokens(auth_client):
    """Reject missing or invalid cookies without returning a private account field."""
    client, service = auth_client
    missing_response = client.get("/api/v1/auth/me")
    service.get_authenticated_user.side_effect = AuthenticationError("Invalid token.")
    client.set_cookie("access_token", "invalid-token")

    invalid_response = client.get("/api/v1/auth/me")

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401
    service.get_authenticated_user.assert_called_once_with("invalid-token")


def test_logout_expires_only_the_auth_cookie_without_auth_service_mutation(auth_client):
    """Clear the browser cookie without invoking account or persistence actions."""
    client, service = auth_client
    client.set_cookie("access_token", TEST_TOKEN, path="/api/v1")

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers["Set-Cookie"]
    assert "access_token=;" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/api/v1" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    service.get_authenticated_user.assert_not_called()


def test_login_and_logout_mark_auth_cookie_secure_when_enabled(secure_auth_client):
    """Set Secure on authentication cookies when the validated setting enables it."""
    client, _ = secure_auth_client

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "attendee@example.test", "password": "correct-password"},
    )
    logout_response = client.post("/api/v1/auth/logout")

    assert "Secure" in login_response.headers["Set-Cookie"]
    assert "Secure" in logout_response.headers["Set-Cookie"]
