"""Provide decorators that require a valid authenticated user."""

from functools import wraps

from flask import current_app, g, request

from app.api.auth import ACCESS_TOKEN_COOKIE_NAME
from app.api.responses import error_response
from app.core.exceptions import AuthenticationError, TokenConfigurationError
from app.dependencies import get_auth_service


def token_required(view_function):
    """Reject requests without a valid access cookie and attach the domain user."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        if not token:
            return error_response(
                "authentication_required", "Authentication is required.", 401
            )

        try:
            g.current_user = get_auth_service().get_authenticated_user(token)
        except AuthenticationError:
            return error_response("invalid_token", "Authentication is required.", 401)
        except TokenConfigurationError:
            current_app.logger.error("JWT signing key is not configured.")
            return error_response(
                "authentication_unavailable", "Authentication is unavailable.", 503
            )

        return view_function(*args, **kwargs)

    return wrapped_view
