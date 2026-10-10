"""Register consistent API responses for Flask and unexpected errors."""

from http import HTTPStatus

from flask import Flask, current_app, g, request
from werkzeug.exceptions import HTTPException

from app.api.responses import error_response
from app.observability.logging import get_logger

HTTP_ERROR_CODES = {
    HTTPStatus.BAD_REQUEST: "bad_request",
    HTTPStatus.UNAUTHORIZED: "unauthorized",
    HTTPStatus.FORBIDDEN: "forbidden",
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.CONFLICT: "conflict",
    HTTPStatus.UNPROCESSABLE_ENTITY: "validation_error",
}


def register_error_handlers(app: Flask) -> None:
    """Return safe JSON for HTTP exceptions and unexpected request failures."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Keep Flask's status and protocol headers while using the API error shape."""
        status_code = error.code or HTTPStatus.INTERNAL_SERVER_ERROR
        try:
            status = HTTPStatus(status_code)
        except ValueError:
            status = None
        code = HTTP_ERROR_CODES.get(status, "http_error")
        if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            get_logger("http").error(
                "HTTP server error.",
                extra={
                    "service": current_app.config.get(
                        "SERVICE_NAME", "mis-eventos-backend"
                    ),
                    "environment": current_app.config.get("APP_ENVIRONMENT", "local"),
                    "version": current_app.config.get("APP_VERSION", "unknown"),
                    "request_id": getattr(g, "request_id", None),
                    "method": request.method,
                    "route": request.url_rule.rule if request.url_rule else "unmatched",
                    "status_code": status_code,
                    "stage": "request_handler",
                },
            )
        message = (
            error.description
            if status_code < HTTPStatus.INTERNAL_SERVER_ERROR
            else "An unexpected error occurred."
        )
        response, _ = error_response(code, message, status_code)
        response.status_code = status_code
        response.headers.update(
            {
                name: value
                for name, value in error.get_response().headers
                if name.lower() not in {"content-type", "content-length"}
            }
        )
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Log unexpected failures once and hide their details from the client."""
        get_logger("http").exception(
            "Unhandled request exception.",
            extra={
                "service": current_app.config.get(
                    "SERVICE_NAME", "mis-eventos-backend"
                ),
                "environment": current_app.config.get("APP_ENVIRONMENT", "local"),
                "version": current_app.config.get("APP_VERSION", "unknown"),
                "request_id": getattr(g, "request_id", None),
                "method": request.method,
                "route": request.url_rule.rule if request.url_rule else "unmatched",
                "stage": "request_handler",
            },
        )
        return error_response(
            "internal_error",
            "An unexpected error occurred.",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
