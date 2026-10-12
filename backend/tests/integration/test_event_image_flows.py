"""Exercise the event image API with real persistence and a mocked R2 client."""

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
R2_CONFIG = {
    "R2_ACCOUNT_ID": "account-test",
    "R2_ACCESS_KEY_ID": "access-test",
    "R2_SECRET_ACCESS_KEY": "secret-test",
    "R2_BUCKET_NAME": "event-images",
    "R2_PUBLIC_BASE_URL": "https://images.example.test",
}
pytestmark = pytest.mark.integration


@pytest.fixture
def event_image_client(monkeypatch):
    """Run the real Flask app, SQLAlchemy repositories, and SQLite in memory."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)
    for key, value in R2_CONFIG.items():
        monkeypatch.setenv(key, value)
    storage = Mock()
    storage.delete_objects.return_value = {"Deleted": []}
    monkeypatch.setattr(
        "app.infrastructure.storage.r2.boto3.client", Mock(return_value=storage)
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
    yield client, app, storage

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
    client, app, storage = event_image_client

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
    assert storage.put_object.call_count == image_count
    assert all(
        call.kwargs["ContentType"] == "image/webp"
        and Image.open(BytesIO(call.kwargs["Body"])).format == "WEBP"
        for call in storage.put_object.call_args_list
    )
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert len(rows) == image_count
        assert [row.position for row in rows] == list(range(image_count))
        assert all(row.url.startswith(R2_CONFIG["R2_PUBLIC_BASE_URL"]) for row in rows)
        assert all(row.storage_key.endswith(".webp") for row in rows)


def test_update_replaces_gallery_after_database_commit(event_image_client):
    client, app, storage = event_image_client
    created = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file(), _image_file("blue")]),
        content_type="multipart/form-data",
    )
    event_id = created.json["event"]["id"]
    # Object keys are available in persistence; API responses expose only public URLs.
    with app.app_context():
        old_rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        previous_keys = {row.storage_key for row in old_rows}

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
    assert {
        item["Key"]
        for item in storage.delete_objects.call_args.kwargs["Delete"]["Objects"]
    } == previous_keys
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert len(rows) == 1
        assert rows[0].storage_key not in previous_keys


def test_failed_second_upload_cleans_objects_and_does_not_create_event(
    event_image_client,
):
    client, app, storage = event_image_client
    storage.put_object.side_effect = [None, RuntimeError("R2 unavailable")]

    response = client.post(
        "/api/v1/events",
        data=_multipart(_event_values(), [_image_file(), _image_file("blue")]),
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json["error"]["code"] == "image_storage_unavailable"
    assert storage.delete_objects.call_count == 1
    assert len(storage.delete_objects.call_args.kwargs["Delete"]["Objects"]) == 2
    with app.app_context():
        assert db.session.query(Event).count() == 0
        assert db.session.query(EventImage).count() == 0


def test_invalid_file_is_rejected_before_upload(event_image_client):
    client, app, storage = event_image_client

    response = client.post(
        "/api/v1/events",
        data={
            "event": json.dumps(_event_values()),
            "images": [(BytesIO(b"not an image"), "bad.png")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    storage.put_object.assert_not_called()
    with app.app_context():
        assert db.session.query(Event).count() == 0


def test_database_failure_cleans_uploaded_images_and_keeps_old_gallery(
    event_image_client, monkeypatch
):
    client, app, storage = event_image_client
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
    assert storage.delete_objects.call_count == 1
    assert len(storage.delete_objects.call_args.kwargs["Delete"]["Objects"]) == 1
    with app.app_context():
        rows = SQLAlchemyEventImageRepository(db.session).list_by_event(event_id)
        assert [row.storage_key for row in rows] == [old_key]
