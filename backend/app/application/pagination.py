"""Validate pagination values consistently across application listing services."""

from app.core.exceptions import ValidationError


def positive_integer(value: object, field_name: str, default: int, maximum: int) -> int:
    """Parse a positive integer pagination value within the configured limit."""
    if value is None:
        return default
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or len(value) > len(str(maximum))
    ):
        raise ValidationError(f"{field_name} must be a positive integer.")
    parsed_value = int(value)
    if parsed_value < 1 or parsed_value > maximum:
        raise ValidationError(f"{field_name} must be between 1 and {maximum}.")
    return parsed_value
