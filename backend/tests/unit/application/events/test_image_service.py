"""Verify image upload compensation preserves provider failures safely."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.application.events.image_service import EventImageService
from app.core.exceptions import EventImageStorageError


def _image() -> BytesIO:
    stream = BytesIO()
    Image.new("RGB", (8, 8), color="red").save(stream, format="PNG")
    stream.seek(0)
    return stream


def _uploaded(public_id: str) -> dict[str, str]:
    return {
        "public_id": public_id,
        "secure_url": f"https://res.cloudinary.test/{public_id}.webp",
    }


def test_stage_uploads_webp_and_returns_confirmed_public_id():
    storage = Mock()
    storage.upload.side_effect = lambda content, public_id: _uploaded(public_id)
    service = EventImageService(Mock(), lambda: storage)

    staged = service.stage([_image()])

    assert len(staged.records) == 1
    assert staged.records[0].storage_key.startswith("mis-eventos/events/")
    assert staged.records[0].url.startswith("https://")
    assert storage.upload.call_args.args[0][:4] == b"RIFF"
    storage.delete.assert_not_called()


def test_upload_failure_cleans_only_previously_confirmed_uploads():
    storage = Mock()
    successful_id = None

    def upload(content, public_id):
        nonlocal successful_id
        if successful_id is None:
            successful_id = public_id
            return _uploaded(public_id)
        raise RuntimeError("provider upload failure")

    storage.upload.side_effect = upload
    service = EventImageService(Mock(), lambda: storage)

    with pytest.raises(EventImageStorageError) as raised:
        service.stage([_image(), _image()])

    assert isinstance(raised.value.__cause__, RuntimeError)
    assert str(raised.value.__cause__) == "provider upload failure"
    storage.delete.assert_called_once_with(successful_id)


def test_cleanup_failure_does_not_mask_upload_error_or_log_sensitive_message(caplog):
    original_error = RuntimeError("upload failed with secret-upload-value")
    cleanup_error = RuntimeError("cleanup failed with secret-cleanup-value")
    storage = Mock()
    calls = 0

    def upload(content, public_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _uploaded(public_id)
        raise original_error

    storage.upload.side_effect = upload
    storage.delete.side_effect = cleanup_error
    service = EventImageService(Mock(), lambda: storage)

    with pytest.raises(EventImageStorageError) as raised:
        service.stage([_image(), _image()])

    assert raised.value.__cause__ is original_error
    assert "secret-upload-value" not in caplog.text
    assert "secret-cleanup-value" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert "Could not remove stored event images" in caplog.text
