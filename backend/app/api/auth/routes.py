"""Expose account registration, login, and authenticated profile endpoints."""

from http import HTTPStatus

from flask import Blueprint, current_app, g, jsonify, request

from app.api.auth import ACCESS_TOKEN_COOKIE_NAME
from app.api.auth.decorators import token_required
from app.api.responses import error_response
from app.core.exceptions import (
    AuthenticationError,
    DuplicateAccountError,
    TokenConfigurationError,
    ValidationError,
)
from app.dependencies import get_auth_service
from app.domain.entities.user_account import UserAccount

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register_user():
    """Validate and create an attendee account without returning credentials."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response(
            "invalid_request", "A JSON object is required.", HTTPStatus.BAD_REQUEST
        )

    try:
        account = get_auth_service().register(
            email=request_data.get("email"),
            password=request_data.get("password"),
            first_name=request_data.get("first_name"),
            last_name=request_data.get("last_name"),
        )
    except ValidationError as error:
        return error_response("validation_error", str(error), HTTPStatus.BAD_REQUEST)
    except DuplicateAccountError as error:
        return error_response("account_exists", str(error), HTTPStatus.CONFLICT)

    return jsonify({"user": _public_user(account)}), HTTPStatus.CREATED


@auth_bp.post("/login")
def login_user():
    """Verify credentials and set an expiring HttpOnly access-token cookie."""
    request_data = request.get_json(silent=True)
    if not isinstance(request_data, dict):
        return error_response(
            "invalid_request", "A JSON object is required.", HTTPStatus.BAD_REQUEST
        )

    try:
        account, token = get_auth_service().authenticate(
            email=request_data.get("email"),
            password=request_data.get("password"),
        )
    except AuthenticationError:
        return error_response(
            "invalid_credentials",
            "Email or password is incorrect.",
            HTTPStatus.UNAUTHORIZED,
        )
    except TokenConfigurationError:
        current_app.logger.error("JWT signing key is not configured.")
        return error_response(
            "authentication_unavailable",
            "Authentication is unavailable.",
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    response = jsonify({"user": _public_user(account)})
    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        token,
        max_age=current_app.config["JWT_ACCESS_TOKEN_TTL_SECONDS"],
        httponly=True,
        secure=current_app.config["JWT_COOKIE_SECURE"],
        samesite="Lax",
        path="/api/v1",
    )
    return response, HTTPStatus.OK


@auth_bp.get("/me")
@token_required
def get_current_user():
    """Return the authenticated user's public profile."""
    return jsonify({"user": _public_user(g.current_user)}), HTTPStatus.OK


@auth_bp.post("/logout")
def logout_user():
    """Expire the browser's authentication cookie without changing stored data."""
    response = current_app.response_class(status=HTTPStatus.NO_CONTENT)
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        path="/api/v1",
        secure=current_app.config["JWT_COOKIE_SECURE"],
        httponly=True,
        samesite="Lax",
    )
    return response


def _public_user(account: UserAccount) -> dict[str, int | str]:
    """Serialize public account fields while excluding password hashes."""
    return {
        "id": account.id,
        "email": account.email,
        "first_name": account.first_name,
        "last_name": account.last_name,
    }
