"""Expose session scheduling endpoints nested under their parent events."""

from flask import Blueprint, jsonify, request

from app.api.auth.decorators import token_required
from app.api.responses import error_response
from app.application.sessions.service import SESSION_FIELDS
from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import get_session_service
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
        session = get_session_service().create(event_id, values)
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    return jsonify({"session": _serialize(session)}), 201


@session_bp.get("/events/<int:event_id>/sessions")
def list_sessions(event_id: int):
    """Return the sessions scheduled for an existing event."""
    try:
        sessions = get_session_service().list_by_event(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    return jsonify({"sessions": [_serialize(session) for session in sessions]}), 200


@session_bp.get("/events/<int:event_id>/sessions/<int:session_id>")
def get_session(event_id: int, session_id: int):
    """Return a session only when it belongs to the event in the URL."""
    try:
        session = get_session_service().get(event_id, session_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    return jsonify({"session": _serialize(session)}), 200


@session_bp.patch("/events/<int:event_id>/sessions/<int:session_id>")
@token_required
def update_session(event_id: int, session_id: int):
    """Partially update a session belonging to the requested event."""
    values = _request_values()
    if isinstance(values, tuple):
        return values
    try:
        session = get_session_service().update(event_id, session_id, values)
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    return jsonify({"session": _serialize(session)}), 200


@session_bp.delete("/events/<int:event_id>/sessions/<int:session_id>")
@token_required
def delete_session(event_id: int, session_id: int):
    """Delete a session without deleting its parent event or speaker profiles."""
    try:
        get_session_service().delete(event_id, session_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    return "", 204


def _request_values() -> dict[str, object] | tuple:
    """Validate the JSON object and reject fields outside the session contract."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("invalid_request", "A JSON object is required.", 400)
    unknown_fields = sorted(set(data) - SESSION_FIELDS)
    if unknown_fields:
        fields = ", ".join(unknown_fields)
        return error_response("invalid_request", f"Unknown field(s): {fields}.", 400)
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
    }
