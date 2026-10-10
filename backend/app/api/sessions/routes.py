"""Expose session scheduling endpoints nested under their parent events."""

from http import HTTPStatus

from flask import Blueprint, g, jsonify, request

from app.api.auth.decorators import token_required
from app.api.responses import concurrency_conflict_response, error_response
from app.application.sessions.service import SESSION_FIELDS
from app.core.exceptions import (
    AuthorizationError,
    CapacityExceededError,
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    NotFoundError,
    ValidationError,
)
from app.dependencies import get_session_attendee_service, get_session_service
from app.domain.entities.session_record import SessionRecord

session_bp = Blueprint("sessions", __name__)


@session_bp.post("/events/<int:event_id>/sessions")
@token_required
def create_session(event_id: int):
    """Create a scheduled session under the requested event."""
    values = _request_values()
    if isinstance(values, tuple):
        return values
    try:
        session = get_session_service().create(
            event_id, values, creator_id=g.current_user.id
        )
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify({"session": _serialize(session)}), HTTPStatus.CREATED


@session_bp.get("/events/<int:event_id>/sessions")
def list_sessions(event_id: int):
    """Return the sessions scheduled for an existing event."""
    try:
        sessions = get_session_service().list_by_event(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify(
        {"sessions": [_serialize(session) for session in sessions]}
    ), HTTPStatus.OK


@session_bp.get("/events/<int:event_id>/sessions/<int:session_id>")
def get_session(event_id: int, session_id: int):
    """Return a session only when it belongs to the event in the URL."""
    try:
        session = get_session_service().get(event_id, session_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify({"session": _serialize(session)}), HTTPStatus.OK


@session_bp.patch("/events/<int:event_id>/sessions/<int:session_id>")
@token_required
def update_session(event_id: int, session_id: int):
    """Partially update a session belonging to the requested event."""
    values = _request_values(require_version=True)
    if isinstance(values, tuple):
        return values
    expected_version = values.pop("version")
    try:
        session = get_session_service().update(
            event_id, session_id, values, expected_version, creator_id=g.current_user.id
        )
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)
    except ConcurrencyConflictError as error:
        return concurrency_conflict_response(str(error), error.current_version)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify({"session": _serialize(session)}), HTTPStatus.OK


@session_bp.delete("/events/<int:event_id>/sessions/<int:session_id>")
@token_required
def delete_session(event_id: int, session_id: int):
    """Delete a session without deleting its parent event or speaker profiles."""
    try:
        get_session_service().delete(event_id, session_id, creator_id=g.current_user.id)
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return "", HTTPStatus.NO_CONTENT


@session_bp.get("/events/<int:event_id>/sessions/<int:session_id>/attendees")
@token_required
def list_session_attendees(event_id: int, session_id: int):
    """List session attendees for the event creator only."""
    try:
        attendees = get_session_attendee_service().list_attendees(
            event_id, session_id, g.current_user.id
        )
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify(
        {"attendees": [_serialize_attendee(item) for item in attendees]}
    ), HTTPStatus.OK


@session_bp.get("/events/<int:event_id>/sessions/<int:session_id>/capacity")
def get_session_occupancy(event_id: int, session_id: int):
    """Return session capacity and active session enrollment counts."""
    try:
        occupancy = get_session_attendee_service().get_occupancy(event_id, session_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify(
        {
            "capacity": occupancy.capacity,
            "occupied": occupancy.occupied,
            "available": occupancy.available,
        }
    ), HTTPStatus.OK


@session_bp.post("/events/<int:event_id>/sessions/<int:session_id>/attendees")
@token_required
def enroll_in_session(event_id: int, session_id: int):
    """Enroll the authenticated attendee without accepting another user ID."""
    try:
        get_session_attendee_service().enroll(event_id, session_id, g.current_user.id)
    except CapacityExceededError as error:
        return error_response("capacity_exceeded", str(error), HTTPStatus.CONFLICT)
    except DuplicateRegistrationError as error:
        return error_response("duplicate_registration", str(error), HTTPStatus.CONFLICT)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify({"message": "Session registration is active."}), HTTPStatus.CREATED


@session_bp.delete("/events/<int:event_id>/sessions/<int:session_id>/attendees/me")
@token_required
def cancel_session_registration(event_id: int, session_id: int):
    """Cancel only the authenticated attendee's own session enrollment."""
    try:
        get_session_attendee_service().cancel(event_id, session_id, g.current_user.id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return "", HTTPStatus.NO_CONTENT


def _request_values(require_version: bool = False) -> dict[str, object] | tuple:
    """Validate the JSON object and reject fields outside the session contract."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response(
            "invalid_request", "A JSON object is required.", HTTPStatus.BAD_REQUEST
        )
    allowed_fields = SESSION_FIELDS | ({"version"} if require_version else set())
    unknown_fields = sorted(set(data) - allowed_fields)
    if unknown_fields:
        fields = ", ".join(unknown_fields)
        return error_response(
            "invalid_request", f"Unknown field(s): {fields}.", HTTPStatus.BAD_REQUEST
        )
    if require_version:
        version = data.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            return error_response(
                "invalid_request",
                "A positive integer version is required.",
                HTTPStatus.BAD_REQUEST,
            )
    return data


def _serialize(session: SessionRecord) -> dict[str, object]:
    """Serialize public session values without exposing persistence internals."""
    return {
        "id": session.id,
        "event_id": session.event_id,
        "title": session.title,
        "description": session.description,
        "starts_at": session.starts_at.isoformat(),
        "ends_at": session.ends_at.isoformat(),
        "capacity": session.capacity,
        "speaker_ids": list(session.speaker_ids),
        "version": session.version,
    }


def _serialize_attendee(attendee) -> dict[str, object]:
    """Serialize roster identity and enrollment time for the event creator."""
    return {
        "user_id": attendee.user_id,
        "first_name": attendee.first_name,
        "last_name": attendee.last_name,
        "email": attendee.email,
        "registered_at": attendee.registered_at.isoformat(),
    }
