import functools

import structlog
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import CompilerElement

from orchestrator.db import db

logger = structlog.get_logger(__name__)


def to_sql_string(stmt: CompilerElement) -> str:
    dialect = postgresql.dialect()  # type: ignore
    return str(stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))


@functools.cache
def get_postgres_version() -> int:
    """Returns the Postgres major version as an int."""
    try:
        # The pg_version_num is pg_major_version * 10000 + pg_minor_version
        pg_version_num = int(db.session.scalar(text("show server_version_num")))
        return pg_version_num // 10000
    except ValueError:
        logger.error("Unable to query Postgres version")
        return 0
