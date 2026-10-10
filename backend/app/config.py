"""Validate and assemble backend configuration from environment variables."""

import os


def get_database_url() -> str:
    """Return the configured database URL or the local development default."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://mis_eventos:mis_eventos_dev@localhost:5432/mis_eventos",
    )
    if not database_url.strip():
        raise ValueError("DATABASE_URL must not be empty.")
    return database_url


def load_config() -> dict[str, object]:
    """Read runtime settings and reject malformed required numeric values."""
    try:
        token_ttl = int(os.getenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "3600"))
    except ValueError as error:
        raise ValueError("JWT_ACCESS_TOKEN_TTL_SECONDS must be an integer.") from error
    if token_ttl <= 0:
        raise ValueError("JWT_ACCESS_TOKEN_TTL_SECONDS must be positive.")

    database_url = get_database_url()
    environment = os.getenv("APP_ENVIRONMENT", "local").strip().lower()
    secure_cookie_value = os.getenv("JWT_COOKIE_SECURE")
    if secure_cookie_value is None:
        secure_cookie = environment == "production"
    else:
        normalized_secure_cookie = secure_cookie_value.strip().lower()
        if normalized_secure_cookie not in {"true", "false"}:
            raise ValueError("JWT_COOKIE_SECURE must be either 'true' or 'false'.")
        secure_cookie = normalized_secure_cookie == "true"

    if environment == "production" and not secure_cookie:
        raise ValueError("JWT_COOKIE_SECURE must be true in production.")

    return {
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "JWT_ACCESS_TOKEN_TTL_SECONDS": token_ttl,
        "JWT_COOKIE_SECURE": secure_cookie,
        "SERVICE_NAME": os.getenv("SERVICE_NAME", "mis-eventos-backend"),
        "APP_ENVIRONMENT": environment,
        "APP_VERSION": os.getenv("APP_VERSION", "dev"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }
