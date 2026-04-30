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

import time
from typing import Any, Iterator

import structlog
from strawberry.extensions import SchemaExtension

from orchestrator.core.db import db

logger = structlog.get_logger()


class StatsExtension(SchemaExtension):
    """Gathers various statistics for an executed GraphQL query, which are logged and returned in the extension results.

    Currently gathered statistics:
    - Operation time of the strawberry query
    - Time spent waiting on SQLAlchemy queries
    - Number of executed SQLAlchemy queries
    """

    before: dict[str, Any] | None
    after: dict[str, Any] | None
    start: float | None
    end: float | None

    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.before = None
        self.after = None
        self.start = None
        self.end = None

    def get_results(self) -> dict[str, Any]:
        if self.after is None or self.before is None:
            return {}

        estimated_queries = self.after["queries_completed"] - self.before.get("queries_completed", 0)
        estimated_query_time = self.after["query_time_spent"] - self.before.get("query_time_spent", 0.0)
        operation_time = self.end - self.start if (self.start is not None and self.end is not None) else "n/a"

        return {
            "stats": {
                "db_queries": estimated_queries,
                "db_time": estimated_query_time,
                "operation_time": operation_time,
            }
        }

    def on_operation(self, *args, **kwargs) -> Iterator[None]:  # type: ignore
        self.before = db.session.connection().info.copy()
        self.start = time.time()

        yield

        self.end = time.time()
        self.after = db.session.connection().info.copy()

        stats = self.get_results().get("stats", {})
        logger.info(
            "GraphQL query stats",
            query=self.execution_context.query,
            variables=self.execution_context.variables,
            **stats,
        )
