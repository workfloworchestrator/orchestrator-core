# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
