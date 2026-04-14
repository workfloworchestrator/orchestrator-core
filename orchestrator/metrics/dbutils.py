from contextlib import contextmanager
from typing import Generator, TypeVar

import structlog
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import ProgrammingError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@contextmanager
def handle_missing_tables() -> Generator[None, None, None]:
    """Context manager for handling database queries when tables don't exist yet."""
    try:
        yield
    except ProgrammingError as e:
        # Check if this is specifically an UndefinedTable error
        if isinstance(e.orig, psycopg_errors.UndefinedTable):
            logger.error(
                "Database table not found; metrics will be empty. This is expected during initial migrations.",
                exc_info=e,
                error_type="UndefinedTable",
            )
        else:
            # Re-raise if it's a different kind of ProgrammingError
            logger.error(
                "Database programming error encountered",
                exc_info=e,
                error_type=type(e.orig).__name__ if hasattr(e, "orig") else "Unknown",
            )
            raise
