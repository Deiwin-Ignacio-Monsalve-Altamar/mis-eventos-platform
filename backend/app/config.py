"""Validate and assemble backend configuration from environment variables."""

import os

from app.settings import (
    APP_ENVIRONMENT_ENV,
    APP_VERSION_ENV,
    CLOUDINARY_URL_ENV,
    DATABASE_URL_ENV,
    DEFAULT_ACCESS_TOKEN_TTL_SECONDS,
    DEFAULT_APP_ENVIRONMENT,
    DEFAULT_APP_VERSION,
    DEFAULT_DATABASE_URL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_SERVICE_NAME,
    FRONTEND_ORIGIN_ENV,
    JWT_ACCESS_TOKEN_TTL_SECONDS_ENV,
    JWT_COOKIE_SECURE_ENV,
    JWT_SECRET_KEY_ENV,
    LOG_LEVEL_ENV,
    MAX_EVENT_IMAGE_REQUEST_SIZE_BYTES,
    SERVICE_NAME_ENV,
)


def get_database_url() -> str:
    """Return the configured database URL or the local development default."""
    database_url = os.getenv(
        DATABASE_URL_ENV,
        DEFAULT_DATABASE_URL,
    )
    if not database_url.strip():
        raise ValueError(f"{DATABASE_URL_ENV} must not be empty.")
    return database_url


def load_config() -> dict[str, object]:
    """Read runtime settings and reject malformed required numeric values."""
    try:
        token_ttl = int(
            os.getenv(
                JWT_ACCESS_TOKEN_TTL_SECONDS_ENV,
                str(DEFAULT_ACCESS_TOKEN_TTL_SECONDS),
            )
        )
    except ValueError as error:
        raise ValueError(
            f"{JWT_ACCESS_TOKEN_TTL_SECONDS_ENV} must be an integer."
        ) from error
    if token_ttl <= 0:
        raise ValueError(f"{JWT_ACCESS_TOKEN_TTL_SECONDS_ENV} must be positive.")

    database_url = get_database_url()
    environment = (
        os.getenv(APP_ENVIRONMENT_ENV, DEFAULT_APP_ENVIRONMENT).strip().lower()
    )
    secure_cookie_value = os.getenv(JWT_COOKIE_SECURE_ENV)
    if secure_cookie_value is None:
        secure_cookie = environment == "production"
    else:
        normalized_secure_cookie = secure_cookie_value.strip().lower()
        if normalized_secure_cookie not in {"true", "false"}:
            raise ValueError(
                f"{JWT_COOKIE_SECURE_ENV} must be either 'true' or 'false'."
            )
        secure_cookie = normalized_secure_cookie == "true"

    if environment == "production" and not secure_cookie:
        raise ValueError(f"{JWT_COOKIE_SECURE_ENV} must be true in production.")

    return {
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "MAX_CONTENT_LENGTH": MAX_EVENT_IMAGE_REQUEST_SIZE_BYTES,
        "JWT_SECRET_KEY": os.getenv(JWT_SECRET_KEY_ENV),
        "JWT_ACCESS_TOKEN_TTL_SECONDS": token_ttl,
        "JWT_COOKIE_SECURE": secure_cookie,
        "FRONTEND_ORIGIN": os.getenv(FRONTEND_ORIGIN_ENV, "").strip(),
        "SERVICE_NAME": os.getenv(SERVICE_NAME_ENV, DEFAULT_SERVICE_NAME),
        "APP_ENVIRONMENT": environment,
        "APP_VERSION": os.getenv(APP_VERSION_ENV, DEFAULT_APP_VERSION),
        "LOG_LEVEL": os.getenv(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL),
        CLOUDINARY_URL_ENV: os.getenv(CLOUDINARY_URL_ENV, "").strip(),
    }
