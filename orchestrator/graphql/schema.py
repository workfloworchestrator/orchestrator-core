# Copyright 2022-2025 SURF, GÉANT.
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
from collections.abc import Callable, Iterable
from http import HTTPStatus
from pathlib import Path
from typing import Any, Coroutine, Protocol

import strawberry
import structlog
from fastapi.routing import APIRouter
from graphql import GraphQLError
from httpx import HTTPStatusError
from strawberry.extensions import SchemaExtension
from strawberry.fastapi import GraphQLRouter
from strawberry.tools import merge_types
from strawberry.types import ExecutionContext
from strawberry.utils.logging import StrawberryLogger

from nwastdlib.graphql.extensions.deprecation_checker_extension import make_deprecation_checker_extension
from nwastdlib.graphql.extensions.error_handler_extension import ErrorHandlerExtension, ErrorType
from oauth2_lib.fastapi import AuthManager
from oauth2_lib.strawberry import authenticated_field
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.autoregistration import create_subscription_strawberry_type, register_domain_models
from orchestrator.graphql.extensions.model_cache import ModelCacheExtension
from orchestrator.graphql.extensions.stats import StatsExtension
from orchestrator.graphql.mutations.customer_description import CustomerSubscriptionDescriptionMutation
from orchestrator.graphql.mutations.start_process import ProcessMutation
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers import (
    SettingsMutation,
    resolve_customer,
    resolve_process,
    resolve_processes,
    resolve_product_blocks,
    resolve_products,
    resolve_resource_types,
    resolve_settings,
    resolve_subscription,
    resolve_subscriptions,
    resolve_version,
    resolve_workflows,
)
from orchestrator.graphql.schemas import DEFAULT_GRAPHQL_MODELS
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.graphql.schemas.settings import StatusType
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.graphql.schemas.version import VersionType
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.graphql.types import SCALAR_OVERRIDES, OrchestratorContext, ScalarOverrideType, StrawberryModelType
from orchestrator.services.process_broadcast_thread import ProcessDataBroadcastThread
from orchestrator.settings import app_settings

api_router = APIRouter()

logger = structlog.get_logger(__name__)


@strawberry.federation.type(description="Orchestrator queries")
class OrchestratorQuery:
    process: ProcessType | None = authenticated_field(resolver=resolve_process, description="Returns a single process")
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
    subscription: SubscriptionInterface | None = authenticated_field(
        resolver=resolve_subscription, description="Returns a single Subscription"
    )
    subscriptions: Connection[SubscriptionInterface] = authenticated_field(
        resolver=resolve_subscriptions, description="Returns list of subscriptions"
    )
    settings: StatusType = authenticated_field(
        resolver=resolve_settings,
        description="Returns information about cache, workers, and global engine settings",
    )
    version: VersionType = authenticated_field(resolver=resolve_version, description="Returns version information")


@strawberry.federation.type(description="Orchestrator customer Query")
class CustomerQuery:
    customers: Connection[CustomerType] = authenticated_field(
        resolver=resolve_customer, description="Returns default customer information"
    )


Query = merge_types("Query", (OrchestratorQuery, CustomerQuery))
Mutation = merge_types("Mutation", (SettingsMutation, CustomerSubscriptionDescriptionMutation, ProcessMutation))

OrchestratorGraphqlRouter = GraphQLRouter


class OrchestratorSchema(strawberry.federation.Schema):
    def process_errors(
        self,
        errors: list[GraphQLError],
        execution_context: ExecutionContext | None = None,
    ) -> None:
        """Override error processing to reduce verbosity of the logging.

        https://strawberry.rocks/docs/types/schema#handling-execution-errors
        """
        for error in errors:
            error_type = error.extensions.get("error_type") if error.extensions else None
            if (
                isinstance(error.original_error, HTTPStatusError)
                and error.original_error.response.status_code == HTTPStatus.NOT_FOUND
            ):
                message = str(error.original_error).splitlines()[0]  # Strip "For more info"
                StrawberryLogger.logger.debug(message)
            elif error_type in (ErrorType.NOT_AUTHORIZED, ErrorType.NOT_AUTHENTICATED):
                StrawberryLogger.logger.info(error.message)
            else:
                StrawberryLogger.error(error, execution_context)


class ContextGetterFactory(Protocol):
    def __call__(
        self,
        auth_manager: AuthManager,
        graphql_models: StrawberryModelType,
        broadcast_thread: ProcessDataBroadcastThread | None = None,
    ) -> Callable[[], Coroutine[Any, Any, OrchestratorContext]]: ...


def default_context_getter(
    auth_manager: AuthManager,
    graphql_models: StrawberryModelType,
    broadcast_thread: ProcessDataBroadcastThread | None = None,
) -> Callable[[], Coroutine[Any, Any, OrchestratorContext]]:
    async def context_getter() -> OrchestratorContext:
        return OrchestratorContext(
            auth_manager=auth_manager, graphql_models=graphql_models, broadcast_thread=broadcast_thread
        )

    return context_getter


def get_extensions(mutation: Any, query: Any) -> Iterable[type[SchemaExtension]]:
    yield ModelCacheExtension
    yield ErrorHandlerExtension
    if app_settings.ENABLE_GRAPHQL_DEPRECATION_CHECKER:
        yield make_deprecation_checker_extension(query=query, mutation=mutation)
    if app_settings.ENABLE_GRAPHQL_STATS_EXTENSION:
        yield StatsExtension
    if app_settings.ENABLE_GRAPHQL_PROFILING_EXTENSION:
        from strawberry.extensions import pyinstrument

        yield pyinstrument.PyInstrument(report_path=Path("pyinstrument.html"))  # type: ignore


def create_graphql_router(
    auth_manager: AuthManager,
    query: Any = Query,
    mutation: Any = Mutation,
    register_models: bool = True,
    subscription_interface: type = SubscriptionInterface,
    broadcast_thread: ProcessDataBroadcastThread | None = None,
    graphql_models: StrawberryModelType | None = None,
    scalar_overrides: ScalarOverrideType | None = None,
    extensions: list | None = None,
    custom_context_getter: ContextGetterFactory | None = None,
) -> OrchestratorGraphqlRouter:
    scalar_overrides = scalar_overrides if scalar_overrides else dict(SCALAR_OVERRIDES)
    models = graphql_models if graphql_models else dict(DEFAULT_GRAPHQL_MODELS)
    models["subscription"] = create_subscription_strawberry_type(
        "Subscription", SubscriptionModel, subscription_interface
    )

    if register_models:
        models = register_domain_models(subscription_interface, existing_models=models)

    extensions = extensions or list(get_extensions(mutation, query))

    schema = OrchestratorSchema(
        query=query,
        mutation=mutation,
        enable_federation_2=app_settings.FEDERATION_ENABLED,
        types=tuple(models.values()),
        extensions=extensions,
        scalar_overrides=scalar_overrides,
    )

    context_getter_factory = custom_context_getter or default_context_getter
    return OrchestratorGraphqlRouter(
        schema,
        context_getter=context_getter_factory(auth_manager, models, broadcast_thread),  # type: ignore
        graphiql=app_settings.SERVE_GRAPHQL_UI,
    )
