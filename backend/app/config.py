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

    return {
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "JWT_ACCESS_TOKEN_TTL_SECONDS": token_ttl,
        "JWT_COOKIE_SECURE": os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true",
        "SERVICE_NAME": os.getenv("SERVICE_NAME", "mis-eventos-backend"),
        "APP_ENVIRONMENT": os.getenv("APP_ENVIRONMENT", "local"),
        "APP_VERSION": os.getenv("APP_VERSION", "dev"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }
