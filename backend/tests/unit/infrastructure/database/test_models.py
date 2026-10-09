"""Verify SCRUM-11 model metadata without opening a database connection."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.infrastructure.database.models import (
    Event,
    EventSession,
    Registration,
    SessionRegistration,
    Speaker,
)


def test_session_registration_constraints_link_one_parent_and_session():
    """Keep duplicate child registrations and invalid child statuses out of schema."""
    table = SessionRegistration.__table__
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_sql = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    foreign_keys = {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    }

    assert ("session_id", "registration_id") in unique_columns
    assert "status IN ('active', 'cancelled')" in check_sql
    assert (
        "session_id",
        "event_sessions.id",
        "CASCADE",
    ) in foreign_keys
    assert (
        "registration_id",
        "registrations.id",
        "CASCADE",
    ) in foreign_keys


def test_capacity_and_version_models_have_positive_value_constraints():
    """Retain database checks for positive event and session capacities and versions."""
    event_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Event.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    session_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in EventSession.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert event_checks["ck_events_capacity_positive"] == "capacity > 0"
    assert event_checks["ck_events_version_positive"] == "version > 0"
    assert session_checks["ck_event_sessions_capacity_positive"] == "capacity > 0"
    assert session_checks["ck_event_sessions_version_positive"] == "version > 0"


def test_existing_registration_and_speaker_relationships_are_reused():
    """Link session enrollment to existing event and speaker models."""
    assert "session_registrations" in Registration.__table__.metadata.tables
    unique_registration = next(
        constraint
        for constraint in Registration.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert tuple(column.name for column in unique_registration.columns) == (
        "user_id",
        "event_id",
    )
    assert SessionRegistration.event_registration.property.mapper.class_ is Registration
    assert SessionRegistration.session.property.mapper.class_ is EventSession
    assert EventSession.speakers.property.mapper.class_ is Speaker
    assert "delete-orphan" in EventSession.registrations.property.cascade
