"""Verify optional Cloudflare R2 configuration and lazy client creation."""

from unittest.mock import Mock

import pytest

from app.config import load_config
from app.infrastructure.storage.r2 import create_r2_client
from app.main import create_app
from app.settings import (
    R2_ACCESS_KEY_ID_ENV,
    R2_ACCOUNT_ID_ENV,
    R2_BUCKET_NAME_ENV,
    R2_PUBLIC_BASE_URL_ENV,
    R2_SECRET_ACCESS_KEY_ENV,
)

R2_ENVIRONMENT_VARIABLES = (
    R2_ACCOUNT_ID_ENV,
    R2_ACCESS_KEY_ID_ENV,
    R2_SECRET_ACCESS_KEY_ENV,
    R2_BUCKET_NAME_ENV,
    R2_PUBLIC_BASE_URL_ENV,
)


def test_r2_configuration_is_optional_at_application_startup(monkeypatch):
    """Load empty optional R2 values and initialize Flask without an R2 client."""
    for name in R2_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    client_factory = Mock()
    monkeypatch.setattr("boto3.client", client_factory)

    config = load_config()
    app = create_app()

    assert config[R2_ACCOUNT_ID_ENV] == ""
    assert config[R2_PUBLIC_BASE_URL_ENV] == ""
    assert app.config[R2_BUCKET_NAME_ENV] == ""
    client_factory.assert_not_called()


def test_load_config_reads_r2_values_without_validating_until_use(monkeypatch):
    """Retain configured values while allowing R2 to remain unused at startup."""
    expected = {
        R2_ACCOUNT_ID_ENV: "account-123",
        R2_ACCESS_KEY_ID_ENV: "access-id",
        R2_SECRET_ACCESS_KEY_ENV: "private-secret",
        R2_BUCKET_NAME_ENV: "event-images",
        R2_PUBLIC_BASE_URL_ENV: "https://images.example.test",
    }
    for name, value in expected.items():
        monkeypatch.setenv(name, value)

    assert {name: load_config()[name] for name in expected} == expected


def test_r2_client_uses_cloudflare_s3_endpoint_and_configured_credentials(
    monkeypatch,
):
    """Construct the boto3 client with expected R2 settings and make no request."""
    boto_client = Mock(return_value=object())
    monkeypatch.setattr("boto3.client", boto_client)
    config = {
        R2_ACCOUNT_ID_ENV: "account-123",
        R2_ACCESS_KEY_ID_ENV: "access-id",
        R2_SECRET_ACCESS_KEY_ENV: "private-secret",
        R2_BUCKET_NAME_ENV: "event-images",
    }

    result = create_r2_client(config)

    assert result is boto_client.return_value
    boto_client.assert_called_once_with(
        "s3",
        endpoint_url="https://account-123.r2.cloudflarestorage.com",
        aws_access_key_id="access-id",
        aws_secret_access_key="private-secret",
        region_name="auto",
    )


def test_r2_client_rejects_incomplete_configuration_without_secret_values():
    """Report missing setting names without exposing credentials in the error."""
    config = {
        R2_ACCOUNT_ID_ENV: "account-123",
        R2_ACCESS_KEY_ID_ENV: "access-id",
        R2_SECRET_ACCESS_KEY_ENV: "sensitive-test-value",
        R2_BUCKET_NAME_ENV: "",
    }

    with pytest.raises(ValueError, match=R2_BUCKET_NAME_ENV) as error:
        create_r2_client(config)

    assert "sensitive-test-value" not in str(error.value)
