"""Define application exceptions translated into consistent API responses."""


class BusinessRuleError(Exception):
    """Raised when a business rule is violated."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class RelatedRecordsError(Exception):
    """Raised when deleting a record would remove related project data."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthorizationError(Exception):
    """Raised when an authenticated account lacks access to a resource."""


class CapacityExceededError(Exception):
    """Raised when no session seats remain available."""


class EventCapacityExceededError(Exception):
    """Raised when an event has no attendee seats remaining."""


class EventUnavailableError(Exception):
    """Raised when an event is not open for new registrations."""


class DuplicateRegistrationError(Exception):
    """Raised when an account already has an active session registration."""


class ConcurrencyConflictError(Exception):
    """Raised when an update is based on a stale persisted resource version."""

    def __init__(self, message: str, current_version: int | None) -> None:
        """Store the latest version available for client conflict recovery."""
        super().__init__(message)
        self.current_version = current_version


class ValidationError(BusinessRuleError):
    """Raised when submitted account data fails validation."""


class DuplicateAccountError(BusinessRuleError):
    """Raised when an account already exists for the submitted email."""


class TokenConfigurationError(RuntimeError):
    """Raised when the server lacks a valid secret for signing access tokens."""
