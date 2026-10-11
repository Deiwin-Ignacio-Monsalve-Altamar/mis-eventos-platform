"""Expose administrator-only role promotion without a general role editor."""

from http import HTTPStatus

from flask import Blueprint, g, jsonify, request

from app.api.auth.decorators import roles_required, token_required
from app.api.responses import error_response
from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    RoleConflictError,
    ValidationError,
)
from app.dependencies import get_admin_analytics_service, get_administration_service
from app.domain.entities.user_role import UserRole
from app.observability.logging import get_logger

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/dashboard")
@token_required
@roles_required(UserRole.ADMIN)
def admin_dashboard():
    """Return platform-wide aggregate metrics to administrators only."""
    return jsonify(
        {"dashboard": get_admin_analytics_service().dashboard()}
    ), HTTPStatus.OK


@admin_bp.post("/users/<int:user_id>/promote-organizer")
@token_required
@roles_required(UserRole.ADMIN)
def promote_user_to_organizer(user_id: int):
    """Promote an existing attendee without accepting a role from the caller."""
    try:
        user = get_administration_service().promote_to_organizer(
            user_id,
            actor_id=g.current_user.id,
            actor_role=g.current_user.role,
        )
    except ValidationError as error:
        return error_response("invalid_request", str(error), HTTPStatus.BAD_REQUEST)
    except AuthorizationError as error:
        return error_response("forbidden", str(error), HTTPStatus.FORBIDDEN)
    except NotFoundError as error:
        return error_response("not_found", str(error), HTTPStatus.NOT_FOUND)
    except RoleConflictError as error:
        return error_response("role_conflict", str(error), HTTPStatus.CONFLICT)

    get_logger("administration").info(
        "User role promotion completed.",
        extra={"actor_user_id": g.current_user.id, "target_user_id": user.id},
    )
    return jsonify({"user": _public_user(user)}), HTTPStatus.OK


@admin_bp.get("/users")
@token_required
@roles_required(UserRole.ADMIN)
def list_users():
    """Return a minimal, paginated user directory to administrators."""
    try:
        page = get_administration_service().list_users(
            request.args.get("page"),
            request.args.get("page_size"),
            request.args.get("q"),
        )
    except ValidationError as error:
        return error_response("invalid_request", str(error), HTTPStatus.BAD_REQUEST)

    return jsonify(
        {
            "users": [_public_user(user) for user in page.users],
            "pagination": {
                "page": page.page,
                "page_size": page.page_size,
                "total": page.total,
                "total_pages": (page.total + page.page_size - 1) // page.page_size,
            },
        }
    ), HTTPStatus.OK


def _public_user(user) -> dict[str, int | str]:
    """Serialize identity fields that are safe to return after promotion."""
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role.value,
    }
