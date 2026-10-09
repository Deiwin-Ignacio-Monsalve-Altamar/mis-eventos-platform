"""Build consistent JSON error responses for API endpoints."""

from flask import jsonify


def error_response(code: str, message: str, status_code: int):
    """Return a standard API error payload with its HTTP status."""
    return jsonify({"error": {"code": code, "message": message}}), status_code
