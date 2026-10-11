"""Exercise public draft visibility against the real SQLite-backed application."""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest

from app.core.security import create_access_token
from app.extensions import db
from app.infrastructure.database.models import Event, EventSession, User
from app.main import create_app

TEST_SECRET = "integration-test-secret-that-is-long-enough"


@pytest.fixture
def public_event_client(monkeypatch):
    """Build the real application and persistence stack with an isolated database."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("FRONTEND_ORIGIN", "")
    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        from app.infrastructure.database import models  # noqa: F401

        db.create_all()
        organizer = User(
            email="organizer@example.test",
            password_hash="unused-in-this-test",
            first_name="Olivia",
            last_name="Organizer",
            role="ORGANIZER",
        )
        admin = User(
            email="admin@example.test",
            password_hash="unused-in-this-test",
            first_name="Avery",
            last_name="Admin",
            role="ADMIN",
        )
        attendee = User(
            email="attendee@example.test",
            password_hash="unused-in-this-test",
            first_name="Taylor",
            last_name="Attendee",
            role="ATTENDEE",
        )
        db.session.add_all([organizer, admin, attendee])
        db.session.flush()

        def add_event(title, status, day):
            event = Event(
                title=title,
                description=f"Description for {title}",
                location="Bogota",
                starts_at=datetime(2030, 1, day, 10, tzinfo=UTC),
                ends_at=datetime(2030, 1, day, 12, tzinfo=UTC),
                capacity=10,
                status=status,
                created_by_id=organizer.id,
            )
            db.session.add(event)
            db.session.flush()
            session = EventSession(
                event_id=event.id,
                title=f"{title} session",
                starts_at=datetime(2030, 1, day, 10, tzinfo=UTC),
                ends_at=datetime(2030, 1, day, 11, tzinfo=UTC),
                capacity=5,
            )
            db.session.add(session)
            db.session.flush()
            return event.id, session.id

        published_one = add_event("Published Alpha", "published", 1)
        published_two = add_event("Published Beta", "published", 2)
        draft = add_event("Private Draft", "draft", 3)
        db.session.commit()
        identifiers = {
            "organizer": organizer.id,
            "admin": admin.id,
            "attendee": attendee.id,
            "published_one": published_one,
            "published_two": published_two,
            "draft": draft,
        }

    yield app.test_client(), identifiers

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def _authenticate(client, user_id):
    token = create_access_token(user_id, TEST_SECRET, 3600)
    client.set_cookie("access_token", token, path="/api/v1")


def test_public_catalog_filters_drafts_before_search_count_and_pagination(
    public_event_client,
):
    client, ids = public_event_client

    first_page = client.get("/api/v1/events?page=1&page_size=1")
    second_page = client.get("/api/v1/events?page=2&page_size=1")
    draft_search = client.get("/api/v1/events?q=Private%20Draft")
    published_search = client.get("/api/v1/events?q=Published%20Alpha")
    description_search = client.get(
        "/api/v1/events?q=Description%20for%20Published%20Beta"
    )
    location_search = client.get("/api/v1/events?q=Bogota")

    assert first_page.status_code == HTTPStatus.OK
    assert first_page.json["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert second_page.status_code == HTTPStatus.OK
    assert second_page.json["events"][0]["id"] == ids["published_two"][0]
    assert draft_search.json["events"] == []
    assert draft_search.json["pagination"]["total"] == 0
    assert [event["title"] for event in published_search.json["events"]] == [
        "Published Alpha"
    ]
    assert [event["title"] for event in description_search.json["events"]] == [
        "Published Beta"
    ]
    assert location_search.json["pagination"]["total"] == 2


def test_public_event_session_and_capacity_reads_hide_drafts(public_event_client):
    client, ids = public_event_client
    draft_id, draft_session_id = ids["draft"]
    published_id, published_session_id = ids["published_one"]

    hidden_responses = [
        client.get(f"/api/v1/events/{draft_id}"),
        client.get(f"/api/v1/events/{draft_id}/capacity"),
        client.get(f"/api/v1/events/{draft_id}/sessions"),
        client.get(f"/api/v1/events/{draft_id}/sessions/{draft_session_id}"),
        client.get(f"/api/v1/events/{draft_id}/sessions/{draft_session_id}/capacity"),
    ]
    assert [response.status_code for response in hidden_responses] == [
        HTTPStatus.NOT_FOUND
    ] * len(hidden_responses)
    assert all(
        "Private Draft" not in response.get_data(as_text=True)
        for response in hidden_responses
    )

    assert client.get(f"/api/v1/events/{published_id}").status_code == HTTPStatus.OK
    assert (
        client.get(f"/api/v1/events/{published_id}/capacity").status_code
        == HTTPStatus.OK
    )
    assert (
        client.get(f"/api/v1/events/{published_id}/sessions").status_code
        == HTTPStatus.OK
    )
    assert (
        client.get(
            f"/api/v1/events/{published_id}/sessions/{published_session_id}"
        ).status_code
        == HTTPStatus.OK
    )


def test_recommendations_exclude_drafts_and_private_management_retains_access(
    public_event_client,
):
    client, ids = public_event_client
    _authenticate(client, ids["attendee"])
    recommendations = client.get("/api/v1/events/recommendations/me")
    titles = [
        item["event"]["title"] for item in recommendations.json["recommendations"]
    ]
    assert recommendations.status_code == HTTPStatus.OK
    assert titles == ["Published Alpha", "Published Beta"]

    _authenticate(client, ids["organizer"])
    private_detail = client.get(f"/api/v1/events/mine/{ids['draft'][0]}")
    private_list = client.get("/api/v1/events/mine?status=draft")
    assert private_detail.status_code == HTTPStatus.OK
    assert private_detail.json["event"]["status"] == "draft"
    assert private_list.status_code == HTTPStatus.OK
    assert any(item["status"] == "draft" for item in private_list.json["events"])

    _authenticate(client, ids["admin"])
    private_detail = client.get(f"/api/v1/events/mine/{ids['draft'][0]}")
    assert private_detail.status_code == HTTPStatus.OK
    assert private_detail.json["event"]["status"] == "draft"
