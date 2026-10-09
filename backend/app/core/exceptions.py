class BusinessRuleError(Exception):
    """Raised when a business rule is violated."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class ValidationError(BusinessRuleError):
    """Raised when submitted account data fails validation."""


class DuplicateAccountError(BusinessRuleError):
    """Raised when an account already exists for the submitted email."""


class TokenConfigurationError(RuntimeError):
    """Raised when the server lacks a valid secret for signing access tokens."""
