# Copyright 2022-2023 SURF.
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
from http import HTTPStatus
from typing import Any

import strawberry
import structlog
from fastapi.routing import APIRouter
from graphql import GraphQLError, GraphQLFormattedError
from graphql.error.graphql_error import format_error
from httpx import HTTPStatusError
from starlette.requests import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.types import ExecutionContext, ExecutionResult
from strawberry.utils.logging import StrawberryLogger

from orchestrator.graphql.extensions.deprecation_checker_extension import make_deprecation_checker_extension
from orchestrator.graphql.extensions.ErrorCollectorExtension import ErrorCollectorExtension
from orchestrator.graphql.resolvers.process import resolve_processes
from orchestrator.graphql.schemas.process import Process
from orchestrator.settings import app_settings

api_router = APIRouter()

logger = structlog.get_logger(__name__)


@strawberry.type(description="Orchestrator queries")
class Query:
    processes: list[Process] = strawberry.field(resolve_processes, description="Returns list of processes")


class PythiaGraphqlRouter(GraphQLRouter):
    def __init__(self, schema: strawberry.federation.Schema, **kwargs: Any) -> None:
        super().__init__(schema, **kwargs)

    @staticmethod
    def _format_graphql_error(error: GraphQLError) -> GraphQLFormattedError:
        if isinstance(error.original_error, HTTPStatusError):
            error.extensions["http_status_code"] = {  # type: ignore
                f"{error.original_error.request.url}": error.original_error.response.status_code
            }
        return format_error(error)

    async def process_result(self, request: Request, result: ExecutionResult) -> GraphQLHTTPResponse:
        data: GraphQLHTTPResponse = {"data": result.data}

        if result.errors:
            data["errors"] = [self._format_graphql_error(error) for error in result.errors]

        return data


class CustomSchema(strawberry.federation.Schema):
    def process_errors(
        self,
        errors: list[GraphQLError],
        execution_context: ExecutionContext | None = None,
    ) -> None:
        """Override error processing to reduce verbosity of the logging.

        https://strawberry.rocks/docs/types/schema#handling-execution-errors
        """
        for error in errors:
            if (
                isinstance(error.original_error, HTTPStatusError)
                and error.original_error.response.status_code == HTTPStatus.NOT_FOUND
            ):
                message = str(error.original_error).splitlines()[0]  # Strip "For more info"
                StrawberryLogger.logger.debug(message)
            else:
                StrawberryLogger.error(error, execution_context)


schema = CustomSchema(
    query=Query,
    extensions=[ErrorCollectorExtension, make_deprecation_checker_extension(query=Query)],
)


graphql_router = PythiaGraphqlRouter(schema, graphiql=app_settings.SERVE_GRAPHQL_UI)
