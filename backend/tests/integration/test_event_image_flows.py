"""Exercise the event image API with real persistence and mocked Cloudinary calls."""

import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.core.security import create_access_token
from app.extensions import db
from app.infrastructure.database.models import Event, EventImage, User
from app.infrastructure.repositories.sqlalchemy_event_image_repository import (
    SQLAlchemyEventImageRepository,
)
from app.main import create_app

TEST_SECRET = "event-image-test-secret-with-at-least-thirty-two-bytes"
CLOUDINARY_URL = "cloudinary://test-key:test-secret@test-cloud"
pytestmark = pytest.mark.integration


@pytest.fixture
def event_image_client(monkeypatch):
    """Run the real Flask app, SQLAlchemy repositories, and SQLite in memory."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("CLOUDINARY_URL", CLOUDINARY_URL)
    upload = Mock()
    destroy = Mock(return_value={"result": "ok"})

    def upload_webp(content, **options):
        return {
            "public_id": options["public_id"],
            "secure_url": f"https://res.cloudinary.test/{options['public_id']}.webp",
        }

    upload.side_effect = upload_webp
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.uploader.upload",
        upload,
    )
    monkeypatch.setattr(
        "app.infrastructure.storage.cloudinary_storage.cloudinary.uploader.destroy",
        destroy,
    )

    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
        organizer = User(
            email="images-organizer@example.test",
            password_hash="unused-test-value",
            first_name="Image",
            last_name="Organizer",
            role="ORGANIZER",
        )
        db.session.add(organizer)
        db.session.commit()
        organizer_id = organizer.id

    client = app.test_client()
    token = create_access_token(organizer_id, TEST_SECRET, 3600)
    client.set_cookie("access_token", token, path="/api/v1")
    yield client, app, upload, destroy

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def _image_file(color: str = "red") -> BytesIO:
    stream = BytesIO()
    Image.new("RGB", (12, 8), color=color).save(stream, format="PNG")
    stream.seek(0)
    return stream


def _event_values(**values) -> dict[str, object]:
    now = datetime.now(UTC) + timedelta(days=3)
    result = {
        "title": "Image gallery event",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(hours=1)).isoformat(),
        "capacity": 15,
        "status": "published",
    }
    result.update(values)
    return result


def _multipart(values: dict[str, object], images: list[BytesIO]):
    return {
        "event": json.dumps(values),
        "images": [(image, f"image-{index}.png") for index, image in enumerate(images)],
    }


@pytest.mark.parametrize("image_count", [1, 3])
def test_create_event_uploads_single_or_multiple_webp_images(
    event_image_client, image_count
):
    client, app, upload, _ = event_image_client

    response = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file() for _ in range(image_count)]),
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.CREATED
    event_id = response.json["event"]["id"]
    assert [image["position"] for image in response.json["event"]["images"]] == list(
        range(image_count)
    )
    assert upload.call_count == image_count
    assert all(
        call.kwargs["format"] == "webp"
        and call.kwargs["resource_type"] == "image"
        and Image.open(BytesIO(call.args[0].getvalue())).format == "WEBP"
        for call in upload.call_args_list
    )
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert len(rows) == image_count
        assert [row.position for row in rows] == list(range(image_count))
        assert all(row.url.startswith("https://res.cloudinary.test/") for row in rows)
        assert all(row.storage_key.startswith("mis-eventos/events/") for row in rows)
        assert all(row.storage_key in row.url for row in rows)
    detail = client.get(f"/api/v1/events/{event_id}")
    assert detail.status_code == HTTPStatus.OK
    assert detail.json["event"]["images"] == response.json["event"]["images"]


def test_update_replaces_gallery_after_database_commit(event_image_client):
    client, app, _, destroy = event_image_client
    created = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file(), _image_file("blue")]),
        content_type="multipart/form-data",
    )
    event_id = created.json["event"]["id"]
    # Cloudinary public IDs are available in persistence; API exposes public URLs only.
    with app.app_context():
        old_rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
    previous_public_ids = {row.storage_key for row in old_rows}

    updated = client.patch(
        f"/api/v1/events/{event_id}",
        data=_multipart(
            {**_event_values(title="Updated gallery"), "version": 1},
            [_image_file("blue")],
        ),
        content_type="multipart/form-data",
    )

    assert updated.status_code == HTTPStatus.OK
    assert updated.json["event"]["title"] == "Updated gallery"
    assert len(updated.json["event"]["images"]) == 1
    deleted_public_ids = {call.args[0] for call in destroy.call_args_list}
    assert previous_public_ids <= deleted_public_ids
    assert all(
        call.kwargs == {"resource_type": "image", "invalidate": True}
        for call in destroy.call_args_list
    )
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert len(rows) == 1
        assert rows[0].storage_key not in previous_public_ids


def test_failed_second_upload_cleans_only_confirmed_objects_and_does_not_create_event(
    event_image_client,
):
    client, app, upload, destroy = event_image_client

    def fail_second_upload(content, **options):
        if upload.call_count == 2:
            raise RuntimeError("provider failure")
        public_id = options["public_id"]
        return {
            "public_id": public_id,
            "secure_url": f"https://res.cloudinary.test/{public_id}.webp",
        }

    upload.side_effect = fail_second_upload

    response = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file(), _image_file("blue")]),
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json["error"]["code"] == "image_storage_unavailable"
    assert "provider failure" not in response.get_data(as_text=True)
    assert destroy.call_count == 1
    attempted_public_ids = {call.kwargs["public_id"] for call in upload.call_args_list}
    deleted_public_ids = {call.args[0] for call in destroy.call_args_list}
    assert len(deleted_public_ids) == 1
    assert deleted_public_ids < attempted_public_ids
    with app.app_context():
        assert db.session.query(Event).count() == 0
        assert db.session.query(EventImage).count() == 0


def test_invalid_file_is_rejected_before_upload(event_image_client):
    client, app, upload, _ = event_image_client

    response = client.post(
        "/api/v1/events",
        data={
            "event": json.dumps(_event_values()),
            "images": [(BytesIO(b"not an image"), "bad.png")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    upload.assert_not_called()
    with app.app_context():
        assert db.session.query(Event).count() == 0


def test_upload_without_cloudinary_configuration_returns_storage_error(
    event_image_client, monkeypatch
):
    client, _, upload, _ = event_image_client
    monkeypatch.setitem(client.application.config, "CLOUDINARY_URL", "")

    response = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file()]),
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json["error"]["code"] == "image_storage_unavailable"
    assert "test-secret" not in response.get_data(as_text=True)
    upload.assert_not_called()


def test_update_without_images_preserves_existing_gallery(event_image_client):
    client, app, upload, destroy = event_image_client
    created = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file()]),
        content_type="multipart/form-data",
    )
    event_id = created.json["event"]["id"]
    upload.reset_mock()
    destroy.reset_mock()

    updated = client.patch(
        f"/api/v1/events/{event_id}",
        json={**_event_values(title="Updated without images"), "version": 1},
    )

    assert updated.status_code == HTTPStatus.OK
    assert len(updated.json["event"]["images"]) == 1
    upload.assert_not_called()
    destroy.assert_not_called()
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert len(rows) == 1


def test_delete_event_removes_cloudinary_images_after_database_delete(
    event_image_client,
):
    client, app, _, destroy = event_image_client
    created = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file()]),
        content_type="multipart/form-data",
    )
    event_id = created.json["event"]["id"]
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        public_id = rows[0].storage_key

    response = client.delete(f"/api/v1/events/{event_id}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.get_data() == b""
    destroy.assert_called_once_with(public_id, resource_type="image", invalidate=True)
    with app.app_context():
        assert SQLAlchemyEventImageRepository(db.session).list_by_event(event_id) == []


def test_database_failure_cleans_uploaded_images_and_keeps_old_gallery(
    event_image_client, monkeypatch
):
    client, app, _, destroy = event_image_client
    created = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file()]),
        content_type="multipart/form-data",
    )
    event_id = created.json["event"]["id"]
    with app.app_context():
        before = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
    old_key = before[0].storage_key
    monkeypatch.setattr(
        SQLAlchemyEventImageRepository,
        "replace_for_event",
        Mock(side_effect=RuntimeError("database write failed")),
    )

    response = client.patch(
        f"/api/v1/events/{event_id}",
        data=_multipart({**_event_values(), "version": 1}, [_image_file("blue")]),
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert destroy.call_count == 1
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert [row.storage_key for row in rows] == [old_key]
