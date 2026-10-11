"""Verify credentialed CORS is restricted to the configured frontend origin."""

from http import HTTPStatus

import pytest

from app.main import create_app


@pytest.fixture
def cors_client(monkeypatch):
    """Build an app with one explicitly configured browser origin."""
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://events.example.com")
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_cors_allows_configured_frontend_origin_with_credentials(cors_client):
    response = cors_client.get(
        "/api/v1/health", headers={"Origin": "https://events.example.com"}
    )

    assert response.status_code == HTTPStatus.OK
    assert (
        response.headers["Access-Control-Allow-Origin"] == "https://events.example.com"
    )
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "*" not in response.headers["Access-Control-Allow-Origin"]


def test_cors_does_not_allow_an_unconfigured_origin(cors_client):
    response = cors_client.get(
        "/api/v1/health", headers={"Origin": "https://untrusted.example"}
    )

    assert response.status_code == HTTPStatus.OK
    assert "Access-Control-Allow-Origin" not in response.headers
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_cors_preflight_allows_api_methods_and_request_headers(cors_client):
    response = cors_client.options(
        "/api/v1/events",
        headers={
            "Origin": "https://events.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-request-id",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert (
        response.headers["Access-Control-Allow-Origin"] == "https://events.example.com"
    )
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    allowed_headers = response.headers["Access-Control-Allow-Headers"].lower()
    assert "content-type" in allowed_headers
    assert "x-request-id" in allowed_headers


def test_cors_is_limited_to_versioned_api_routes(cors_client):
    response = cors_client.get(
        "/metrics", headers={"Origin": "https://events.example.com"}
    )

    assert response.status_code == HTTPStatus.OK
    assert "Access-Control-Allow-Origin" not in response.headers
