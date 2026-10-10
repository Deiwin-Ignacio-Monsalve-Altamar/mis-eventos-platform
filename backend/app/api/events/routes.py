"""Expose authenticated endpoints for creating and editing events."""

from http import HTTPStatus

from flask import Blueprint, g, jsonify, request

from app.api.auth.decorators import token_required
from app.api.responses import concurrency_conflict_response, error_response
from app.application.dto.event_page import EventPage
from app.application.events.service import EDITABLE_FIELDS
from app.core.exceptions import (
    AuthorizationError,
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    EventCapacityExceededError,
    EventUnavailableError,
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
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)

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
    ), HTTPStatus.OK


@event_bp.get("/events/<int:event_id>")
def get_event(event_id: int):
    """Return a single event or a standard not-found response."""
    try:
        event = get_event_service().get_by_id(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)

    return jsonify({"event": _serialize_event(event)}), HTTPStatus.OK


@event_bp.get("/events/mine")
@token_required
def list_my_events():
    """Return a paginated list scoped to the authenticated event creator."""
    if "creator_id" in request.args or "user_id" in request.args:
        return error_response(
            "invalid_request",
            "Event ownership is determined by the authenticated account.",
            HTTPStatus.BAD_REQUEST,
        )
    try:
        page = get_event_service().list_my_events(
            g.current_user.id,
            request.args.get("page"),
            request.args.get("page_size"),
            request.args.get("q"),
            request.args.get("status"),
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    return jsonify(_serialize_event_page(page)), HTTPStatus.OK


@event_bp.get("/events/mine/summary")
@token_required
def my_event_dashboard():
    """Return status and date metrics for events owned by the current user."""
    return jsonify(
        {"summary": get_event_service().dashboard(g.current_user.id)}
    ), HTTPStatus.OK


@event_bp.get("/events/mine/<int:event_id>")
@token_required
def get_my_event(event_id: int):
    """Return an event-management record only when it belongs to the caller."""
    try:
        event = get_event_service().get_my_event(event_id, g.current_user.id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify({"event": _serialize_event(event)}), HTTPStatus.OK


@event_bp.post("/events")
@token_required
def create_event():
    """Create an event attributed to the authenticated user."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response(
            "invalid_request", "A JSON object is required.", HTTPStatus.BAD_REQUEST
        )

    try:
        event = get_event_service().create(
            _editable_values(request_data), creator_id=g.current_user.id
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)

    return jsonify({"event": _serialize_event(event)}), HTTPStatus.CREATED


@event_bp.patch("/events/<int:event_id>")
@token_required
def update_event(event_id: int):
    """Update supplied fields on an existing event after token validation."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response(
            "invalid_request", "A JSON object is required.", HTTPStatus.BAD_REQUEST
        )
    expected_version = request_data.get("version")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 1
    ):
        return error_response(
            "invalid_request",
            "A positive integer version is required.",
            HTTPStatus.BAD_REQUEST,
        )

    try:
        event = get_event_service().update(
            event_id,
            _editable_values(request_data),
            expected_version,
            creator_id=g.current_user.id,
        )
    except ConcurrencyConflictError as error:
        return concurrency_conflict_response(str(error), error.current_version)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)

    return jsonify({"event": _serialize_event(event)}), HTTPStatus.OK


@event_bp.delete("/events/<int:event_id>")
@token_required
def delete_event(event_id: int):
    """Delete an event when it has no registrations or other related records."""
    try:
        get_event_service().delete(event_id, creator_id=g.current_user.id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    except RelatedRecordsError as error:
        return error_response("related_records", str(error), HTTPStatus.CONFLICT)
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)

    return "", HTTPStatus.NO_CONTENT


@event_bp.get("/registrations/me")
@token_required
def list_my_event_registrations():
    """Return the authenticated user's event registrations and event details."""
    if "user_id" in request.args:
        return error_response(
            "invalid_request",
            "Registrations can only be listed for the current user.",
            HTTPStatus.BAD_REQUEST,
        )
    try:
        page = get_event_registration_service().list_for_user(
            g.current_user.id,
            page=request.args.get("page"),
            page_size=request.args.get("page_size"),
            status=request.args.get("status"),
            period=request.args.get("period"),
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)

    total_pages = (page.total + page.page_size - 1) // page.page_size
    return jsonify(
        {
            "registrations": [
                {
                    "id": registration.id,
                    "status": registration.status,
                    "registered_at": registration.registered_at.isoformat(),
                    "event": _serialize_event(registration.event),
                }
                for registration in page.registrations
            ],
            "pagination": {
                "page": page.page,
                "page_size": page.page_size,
                "total": page.total,
                "total_pages": total_pages,
            },
        }
    ), HTTPStatus.OK


@event_bp.get("/events/<int:event_id>/capacity")
def event_registration_capacity(event_id: int):
    """Return public event capacity using active registrations only."""
    try:
        capacity = get_event_registration_service().capacity_for_event(event_id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    return jsonify(capacity), HTTPStatus.OK


@event_bp.get("/registrations/me/summary")
@token_required
def my_registration_summary():
    """Return attendance counts derived only from the caller's registrations."""
    return jsonify(
        {
            "summary": get_event_registration_service().summary_for_user(
                g.current_user.id
            )
        }
    ), HTTPStatus.OK


@event_bp.post("/events/<int:event_id>/registrations/me")
@token_required
def register_for_event(event_id: int):
    """Register or reactivate the authenticated user's event enrollment."""
    try:
        registration = get_event_registration_service().register(
            event_id, g.current_user.id
        )
    except EventUnavailableError as error:
        return error_response("event_unavailable", str(error), HTTPStatus.CONFLICT)
    except EventCapacityExceededError as error:
        return error_response("capacity_exceeded", str(error), HTTPStatus.CONFLICT)
    except DuplicateRegistrationError as error:
        return error_response("duplicate_registration", str(error), HTTPStatus.CONFLICT)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)

    return jsonify(
        {
            "registration": {
                "id": registration.id,
                "event_id": registration.event_id,
                "user_id": registration.user_id,
                "status": registration.status,
            }
        }
    ), HTTPStatus.CREATED


@event_bp.delete("/events/<int:event_id>/registrations/me")
@token_required
def cancel_event_registration(event_id: int):
    """Cancel the authenticated user's event and active session enrollments."""
    try:
        get_event_registration_service().cancel(event_id, g.current_user.id)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    return "", HTTPStatus.NO_CONTENT


def _editable_values(request_data: dict[str, object]) -> dict[str, object]:
    """Select supported event fields and ignore client-supplied identity fields."""
    return {key: value for key, value in request_data.items() if key in EDITABLE_FIELDS}


def _serialize_event_page(page: EventPage) -> dict[str, object]:
    """Serialize an event page with the established pagination contract."""
    total_pages = (page.total + page.page_size - 1) // page.page_size
    return {
        "events": [_serialize_event(event) for event in page.events],
        "pagination": {
            "page": page.page,
            "page_size": page.page_size,
            "total": page.total,
            "total_pages": total_pages,
        },
    }


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
