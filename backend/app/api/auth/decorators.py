"""Provide decorators that require a valid authenticated user."""

from functools import wraps
from http import HTTPStatus

from flask import current_app, g, request

from app.api.auth import ACCESS_TOKEN_COOKIE_NAME
from app.api.responses import error_response
from app.core.exceptions import AuthenticationError, TokenConfigurationError
from app.dependencies import get_auth_service
from app.domain.entities.user_role import UserRole


def token_required(view_function):
    """Reject requests without a valid access cookie and attach the domain user."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        if not token:
            return error_response(
                "authentication_required",
                "Authentication is required.",
                HTTPStatus.UNAUTHORIZED,
            )

        try:
            g.current_user = get_auth_service().get_authenticated_user(token)
        except AuthenticationError:
            return error_response(
                "invalid_token", "Authentication is required.", HTTPStatus.UNAUTHORIZED
            )
        except TokenConfigurationError:
            current_app.logger.error("JWT signing key is not configured.")
            return error_response(
                "authentication_unavailable",
                "Authentication is unavailable.",
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

        return view_function(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles: UserRole):
    """Require an authenticated database-backed identity to have an allowed role."""

    def decorate(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            account = getattr(g, "current_user", None)
            if account is None:
                return error_response(
                    "authentication_required",
                    "Authentication is required.",
                    HTTPStatus.UNAUTHORIZED,
                )
            if account.role not in allowed_roles:
                return error_response(
                    "forbidden",
                    "The account does not have permission to perform this action.",
                    HTTPStatus.FORBIDDEN,
                )
            return view_function(*args, **kwargs)

        return wrapped_view

    return decorate
