"""Verify Cloudinary configuration is optional and initialized only on use."""

from unittest.mock import Mock

import pytest

from app.config import load_config
from app.infrastructure.storage.cloudinary_storage import (
    CloudinaryStorage,
    create_cloudinary_storage,
)
from app.main import create_app
from app.settings import CLOUDINARY_URL_ENV

TEST_CLOUDINARY_URL = "cloudinary://test-key:test-secret@test-cloud"


def test_cloudinary_configuration_is_optional_at_application_startup(monkeypatch):
    monkeypatch.delenv(CLOUDINARY_URL_ENV, raising=False)
    configure_sdk = Mock()
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.config",
        configure_sdk,
    )

    config = load_config()
    app = create_app()

    assert config[CLOUDINARY_URL_ENV] == ""
    assert app.config[CLOUDINARY_URL_ENV] == ""
    configure_sdk.assert_not_called()


def test_load_config_reads_cloudinary_url_without_configuring_sdk(monkeypatch):
    monkeypatch.setenv(CLOUDINARY_URL_ENV, TEST_CLOUDINARY_URL)
    configure_sdk = Mock()
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.config",
        configure_sdk,
    )

    assert load_config()[CLOUDINARY_URL_ENV] == TEST_CLOUDINARY_URL
    configure_sdk.assert_not_called()


def test_cloudinary_storage_configures_official_sdk_from_cloudinary_url(monkeypatch):
    configure_sdk = Mock()
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.config",
        configure_sdk,
    )

    storage = create_cloudinary_storage({CLOUDINARY_URL_ENV: TEST_CLOUDINARY_URL})

    assert storage is not None
    configure_sdk.assert_called_once_with(
        cloud_name="test-cloud",
        api_key="test-key",
        api_secret="test-secret",
        secure=True,
    )


@pytest.mark.parametrize("response", [{"result": "ok"}, {"result": "not found"}])
def test_delete_uses_image_public_id_and_returns_sdk_response(monkeypatch, response):
    destroy = Mock(return_value=response)
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.uploader.destroy",
        destroy,
    )

    result = CloudinaryStorage().delete("mis-eventos/events/existing-id")

    assert result == response
    destroy.assert_called_once_with(
        "mis-eventos/events/existing-id",
        resource_type="image",
        invalidate=True,
    )


@pytest.mark.parametrize(
    "value", ["", "https://example.test", "cloudinary://key@cloud"]
)
def test_cloudinary_storage_rejects_missing_or_invalid_settings_without_leaking_values(
    value,
):
    with pytest.raises(ValueError) as error:
        create_cloudinary_storage({CLOUDINARY_URL_ENV: value})

    if value:
        assert value not in str(error.value)
