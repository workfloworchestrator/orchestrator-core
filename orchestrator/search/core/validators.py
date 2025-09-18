import uuid

from dateutil.parser import isoparse


def is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def is_iso_date(value: str) -> bool:
    """Check if a string is a valid ISO 8601 date."""
    try:
        isoparse(value)
        return True
    except (ValueError, TypeError):
        return False


def is_bool_string(value: str) -> bool:
    """Check if a string explicitly represents a boolean value with true/false."""

    return value.strip().lower() in {"true", "false"}
