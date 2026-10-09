"""Expose authenticated endpoints for creating and editing events."""

from flask import Blueprint, g, jsonify, request

from app.api.auth.decorators import token_required
from app.api.responses import concurrency_conflict_response, error_response
from app.application.events.service import EDITABLE_FIELDS
from app.core.exceptions import (
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    EventCapacityExceededError,
    NotFoundError,
    RelatedRecordsError,
    ValidationError,
)
from app.dependencies import get_event_registration_service, get_event_service
from app.domain.entities.event_record import EventRecord

event_bp = Blueprint("events", __name__)


@event_bp.get("/events")
def list_events():
    """Return a paginated event list, optionally filtered by a text query."""
    try:
        page = get_event_service().list_events(
            page=request.args.get("page"),
            page_size=request.args.get("page_size"),
            search_query=request.args.get("q"),
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)

    total_pages = (page.total + page.page_size - 1) // page.page_size
    return jsonify(
        {
            "events": [_serialize_event(event) for event in page.events],
            "pagination": {
                "page": page.page,
                "page_size": page.page_size,
                "total": page.total,
                "total_pages": total_pages,
            },
        }
    ), 200


@event_bp.get("/events/<int:event_id>")
def get_event(event_id: int):
    """Return a single event or a standard not-found response."""
    try:
        event = get_event_service().get_by_id(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)

    return jsonify({"event": _serialize_event(event)}), 200


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
    expected_version = request_data.get("version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 1
    ):
        return error_response(
            "invalid_request", "A positive integer version is required.", 400
        )

    try:
        event = get_event_service().update(
            event_id, _editable_values(request_data), expected_version
        )
    except ConcurrencyConflictError as error:
        return concurrency_conflict_response(str(error), error.current_version)
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)

    return jsonify({"event": _serialize_event(event)}), 200


@event_bp.delete("/events/<int:event_id>")
@token_required
def delete_event(event_id: int):
    """Delete an event when it has no registrations or other related records."""
    try:
        get_event_service().delete(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    except RelatedRecordsError as error:
        return error_response("related_records", str(error), 409)

    return "", 204


@event_bp.post("/events/<int:event_id>/registrations/me")
@token_required
def register_for_event(event_id: int):
    """Register or reactivate the authenticated user's event enrollment."""
    try:
        registration = get_event_registration_service().register(
            event_id, g.current_user.id
        )
    except EventCapacityExceededError as error:
        return error_response("capacity_exceeded", str(error), 409)
    except DuplicateRegistrationError as error:
        return error_response("duplicate_registration", str(error), 409)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)

    return jsonify(
        {
            "registration": {
                "id": registration.id,
                "event_id": registration.event_id,
                "user_id": registration.user_id,
                "status": registration.status,
            }
        }
    ), 201


@event_bp.delete("/events/<int:event_id>/registrations/me")
@token_required
def cancel_event_registration(event_id: int):
    """Cancel the authenticated user's event and active session enrollments."""
    try:
        get_event_registration_service().cancel(event_id, g.current_user.id)
    except NotFoundError as error:
        return error_response("not_found", str(error), 404)
    except ValidationError as error:
        return error_response("validation_error", str(error), 400)
    return "", 204


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
        "version": event.version,
    }
