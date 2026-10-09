"""Build consistent JSON error responses for API endpoints."""

from flask import jsonify


def error_response(code: str, message: str, status_code: int):
    """Return a standard API error payload with its HTTP status."""
    return jsonify({"error": {"code": code, "message": message}}), status_code


def concurrency_conflict_response(message: str, current_version: int | None):
    """Return a standard conflict response with the latest resource version."""
    return (
        jsonify(
            {
                "error": {
                    "code": "concurrency_conflict",
                    "message": message,
                    "current_version": current_version,
                }
            }
        ),
        409,
    )
