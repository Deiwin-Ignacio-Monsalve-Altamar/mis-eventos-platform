"""Provide password hashing and signed access-token utilities."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import jwt

from app.core.exceptions import AuthenticationError, TokenConfigurationError

ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
MINIMUM_SECRET_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password with the challenge-required SHA-256 algorithm."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Compare a submitted password hash without timing-sensitive equality."""
    candidate_hash = hash_password(password)
    return hmac.compare_digest(candidate_hash, password_hash)


def create_access_token(
    user_id: int, secret: str | None, expires_in_seconds: int
) -> str:
    """Create an expiring JWT for an authenticated user."""
    signing_key = _validate_signing_key(secret)
    if expires_in_seconds <= 0:
        raise TokenConfigurationError("Access-token lifetime must be positive.")

    issued_at = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=expires_in_seconds),
        "type": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(claims, signing_key, algorithm=ACCESS_TOKEN_ALGORITHM)


def decode_access_token(token: str, secret: str | None) -> int:
    """Validate an access JWT and return its user identifier."""
    signing_key = _validate_signing_key(secret)
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[ACCESS_TOKEN_ALGORITHM],
            options={"require": ["sub", "iat", "exp", "type"]},
        )
        if claims["type"] != ACCESS_TOKEN_TYPE:
            raise AuthenticationError("The access token is invalid.")
        return int(claims["sub"])
    except (jwt.PyJWTError, TypeError, ValueError) as error:
        raise AuthenticationError("The access token is invalid.") from error


def _validate_signing_key(secret: str | None) -> str:
    """Require a sufficiently long environment-provided signing key."""
    if secret is None or len(secret.encode("utf-8")) < MINIMUM_SECRET_BYTES:
        raise TokenConfigurationError(
            "JWT_SECRET_KEY must contain at least 32 bytes of random data."
        )
    return secret
