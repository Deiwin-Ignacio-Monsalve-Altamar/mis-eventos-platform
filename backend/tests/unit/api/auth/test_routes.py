"""Verify authentication routes and their persistence and token behavior."""

import hashlib

import pytest
from flask import Flask

from app.api.auth.routes import auth_bp
from app.extensions import db
from app.infrastructure.database.models import User

TEST_JWT_SECRET = "test-only-signing-secret-with-more-than-32-bytes"


@pytest.fixture
def auth_client():
    """Provide the auth blueprint with an isolated in-memory SQLite database."""
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=TEST_JWT_SECRET,
        JWT_ACCESS_TOKEN_TTL_SECONDS=3600,
        JWT_COOKIE_SECURE=False,
    )
    db.init_app(app)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")

    with app.app_context():
        db.create_all()

    yield app.test_client()

    with app.app_context():
        db.session.remove()
        db.drop_all()


def registration_payload(**overrides):
    """Build a valid registration payload with optional field overrides."""
    payload = {
        "email": "attendee@example.test",
        "password": "correct-horse-battery",
        "first_name": "Alex",
        "last_name": "Rivera",
    }
    payload.update(overrides)
    return payload


def register_account(client, **overrides):
    """Register a valid account and return its HTTP response."""
    return client.post("/api/v1/auth/register", json=registration_payload(**overrides))


def test_registration_stores_sha256_hash_and_returns_public_profile(auth_client):
    """Store only the challenge-required hash and omit credentials from the response."""
    response = register_account(auth_client)

    assert response.status_code == 201
    assert response.json["user"]["email"] == "attendee@example.test"
    assert "password_hash" not in response.json["user"]
    with auth_client.application.app_context():
        user = db.session.query(User).one()
        assert (
            user.password_hash == hashlib.sha256(b"correct-horse-battery").hexdigest()
        )
        assert user.password_hash != "correct-horse-battery"


def test_login_with_valid_credentials_sets_http_only_access_cookie(auth_client):
    """Authenticate a registered account and return its public profile and cookie."""
    register_account(auth_client)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "ATTENDEE@example.test", "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    assert response.json["user"]["email"] == "attendee@example.test"
    assert "password_hash" not in response.json["user"]
    assert "HttpOnly" in response.headers["Set-Cookie"]


def test_login_with_incorrect_credentials_returns_unauthorized(auth_client):
    """Reject incorrect credentials without revealing whether the email exists."""
    register_account(auth_client)

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "attendee@example.test", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_credentials"


def test_registration_rejects_duplicate_normalized_email(auth_client):
    """Reject a second account whose email differs only by case and whitespace."""
    register_account(auth_client)

    response = register_account(auth_client, email=" ATTENDEE@example.test ")

    assert response.status_code == 409
    assert response.json["error"]["code"] == "account_exists"


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"first_name": "  "},
    ],
)
def test_registration_rejects_invalid_input(auth_client, overrides):
    """Return a validation response when account fields are malformed."""
    response = register_account(auth_client, **overrides)

    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"


def test_current_user_rejects_missing_and_invalid_tokens(auth_client):
    """Require a valid access token before returning the current user profile."""
    missing_token_response = auth_client.get("/api/v1/auth/me")
    auth_client.set_cookie("access_token", "invalid-token")
    invalid_token_response = auth_client.get("/api/v1/auth/me")

    assert missing_token_response.status_code == 401
    assert invalid_token_response.status_code == 401
