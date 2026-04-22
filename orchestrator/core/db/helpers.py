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

import functools

import structlog
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import CompilerElement

from orchestrator.core.db import db

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
