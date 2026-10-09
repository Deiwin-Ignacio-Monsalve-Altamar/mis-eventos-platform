"""Expose authenticated endpoints for creating and editing events."""

from flask import Blueprint, g, jsonify, request

from app.api.auth.decorators import token_required
from app.api.responses import error_response
from app.application.events.service import EDITABLE_FIELDS
from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import get_event_service
from app.domain.entities.event_record import EventRecord

event_bp = Blueprint("events", __name__)


@event_bp.post("/events")
@token_required
def create_event():
    """Create an event attributed to the authenticated user."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response("invalid_request", "A JSON object is required.", 400)

    try:
        event = get_event_service().create(
            _editable_values(request_data), creator_id=g.current_user.id
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)

    return jsonify({"event": _serialize_event(event)}), 201


@event_bp.patch("/events/<int:event_id>")
@token_required
def update_event(event_id: int):
    """Update supplied fields on an existing event after token validation."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response("invalid_request", "A JSON object is required.", 400)

    try:
        event = get_event_service().update(event_id, _editable_values(request_data))
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)

    return jsonify({"event": _serialize_event(event)}), 200


def _editable_values(request_data: dict[str, object]) -> dict[str, object]:
    """Select supported event fields and ignore client-supplied identity fields."""
    return {key: value for key, value in request_data.items() if key in EDITABLE_FIELDS}


def _serialize_event(event: EventRecord) -> dict[str, object]:
    """Serialize public event fields without exposing creator internals."""
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "capacity": event.capacity,
        "status": event.status,
    }
