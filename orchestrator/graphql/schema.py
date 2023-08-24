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
from typing import Any, Callable, TypeVar, Union

import strawberry
import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from graphql import GraphQLError, GraphQLFormattedError
from graphql.error.graphql_error import format_error
from httpx import HTTPStatusError
from starlette.requests import Request
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.tools import merge_types
from strawberry.types import ExecutionContext, ExecutionResult
from strawberry.utils.logging import StrawberryLogger

from oauth2_lib.strawberry import authenticated_field
from orchestrator.graphql.extensions.deprecation_checker_extension import make_deprecation_checker_extension
from orchestrator.graphql.extensions.error_collector_extension import ErrorCollectorExtension
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers import (
    SettingsMutation,
    resolve_default_customer,
    resolve_processes,
    resolve_product_blocks,
    resolve_products,
    resolve_resource_types,
    resolve_settings,
    resolve_subscriptions,
    resolve_workflows,
)
from orchestrator.graphql.schemas.default_customer import DefaultCustomerType
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.schemas.product import ProductModelGraphql, ProductType
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.graphql.schemas.settings import StatusType
from orchestrator.graphql.schemas.subscription import Subscription, SubscriptionInterface
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.graphql.types import SCALAR_OVERRIDES, OrchestratorContext
from orchestrator.security import get_oidc_user, get_opa_security_graphql
from orchestrator.settings import app_settings

api_router = APIRouter()

logger = structlog.get_logger(__name__)

StrawberryPydanticModel = TypeVar("StrawberryPydanticModel", bound=StrawberryTypeFromPydantic)
StrawberryModelType = dict[str, StrawberryPydanticModel]

GRAPHQL_MODELS: StrawberryModelType = {"ProductModelGraphql": ProductModelGraphql}


@strawberry.federation.type(description="Orchestrator queries")
class Query:
    processes: Connection[ProcessType] = authenticated_field(
        resolver=resolve_processes, description="Returns list of processes"
    )
    products: Connection[ProductType] = authenticated_field(
        resolver=resolve_products, description="Returns list of products"
    )
    product_blocks: Connection[ProductBlock] = authenticated_field(
        resolver=resolve_product_blocks, description="Returns list of product blocks"
    )
    resource_types: Connection[ResourceType] = authenticated_field(
        resolver=resolve_resource_types, description="Returns list of resource types"
    )
    workflows: Connection[Workflow] = authenticated_field(
        resolver=resolve_workflows, description="Returns list of workflows"
    )
    subscriptions: Connection[SubscriptionInterface] = authenticated_field(
        resolver=resolve_subscriptions, description="Returns list of subscriptions"
    )
    settings: StatusType = authenticated_field(
        resolver=resolve_settings,
        description="Returns information about cache, workers, and global engine settings",
    )
    customers: Connection[DefaultCustomerType] = authenticated_field(
        resolver=resolve_default_customer, description="Returns default customer information"
    )


Mutation = merge_types("Mutation", (SettingsMutation,))


class OrchestratorGraphqlRouter(GraphQLRouter):
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


class OrchestratorSchema(strawberry.federation.Schema):
    def process_errors(
        self,
        errors: list[GraphQLError],
        execution_context: Union[ExecutionContext, None] = None,
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


def custom_context_dependency(
    get_current_user: Callable = Depends(get_oidc_user),  # noqa: B008
    get_opa_decision: Callable = Depends(get_opa_security_graphql),  # noqa: B008
) -> OrchestratorContext:
    return OrchestratorContext(get_current_user=get_current_user, get_opa_decision=get_opa_decision)


async def get_context(custom_context=Depends(custom_context_dependency)) -> OrchestratorContext:  # type: ignore # noqa: B008
    return custom_context


def create_graphql_router(query: Any = Query, mutation: Any = Mutation) -> OrchestratorGraphqlRouter:
    schema = OrchestratorSchema(
        query=query,
        mutation=mutation,
        enable_federation_2=app_settings.FEDEREATION_ENABLED,
        types=(Subscription,) + tuple(GRAPHQL_MODELS.values()),
        extensions=[ErrorCollectorExtension, make_deprecation_checker_extension(query=query)],
        scalar_overrides=SCALAR_OVERRIDES,
    )

    return OrchestratorGraphqlRouter(schema, context_getter=get_context, graphiql=app_settings.SERVE_GRAPHQL_UI)


graphql_router = create_graphql_router()
