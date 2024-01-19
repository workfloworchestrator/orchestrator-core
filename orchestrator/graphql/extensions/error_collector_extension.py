# Copyright 2019-2023 SURF.
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
from collections.abc import Generator
from contextvars import ContextVar

import structlog
from graphql import GraphQLError
from strawberry.extensions import SchemaExtension

logger = structlog.get_logger(__name__)

error_bucket: ContextVar[list[GraphQLError] | None] = ContextVar("error_bucket", default=None)


class ErrorCollectorExtension(SchemaExtension):
    def on_execute(self) -> Generator[None, None, None]:
        error_bucket.set([])

        yield

        result = self.execution_context.result
        if result and (collected_errors := error_bucket.get()):
            if not result.errors:
                result.errors = []
            result.errors.extend(collected_errors)


def register_error(error: GraphQLError) -> None:
    """Register a GraphQLError encountered during the query execution.

    Use this to collect errors from multiple resolvers and return them in the response.
    """
    errors = error_bucket.get()
    if errors is None:
        logger.debug("ErrorCollectorExtension disabled, dropping error", error=error)
        return

    logger.debug("Registering error", error=error)
    errors.append(error)
    error_bucket.set(errors)
