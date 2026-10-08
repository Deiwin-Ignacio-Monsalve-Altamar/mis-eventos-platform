class BusinessRuleError(Exception):
    """Raised when a business rule is violated."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""
