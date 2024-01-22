#!/usr/bin/env python3

# Copyright 2019-2020 SURF.
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
from collections.abc import Callable
from typing import Any

import sentry_sdk
import structlog
import typer
from fastapi.applications import FastAPI
from fastapi_etag.dependency import add_exception_handler
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.strawberry import StrawberryIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, Response

from nwastdlib.logging import ClearStructlogContextASGIMiddleware, initialise_logging
from orchestrator import __version__
from orchestrator.api.api_v1.api import api_router
from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.cli.main import app as cli_app
from orchestrator.db import db, init_database
from orchestrator.db.database import DBSessionMiddleware
from orchestrator.distlock import init_distlock_manager
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.exception_handlers import problem_detail_handler
from orchestrator.graphql import Mutation, Query, create_graphql_router
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.services.processes import ProcessDataBroadcastThread
from orchestrator.settings import AppSettings, ExecutorType, app_settings
from orchestrator.version import GIT_COMMIT_HASH
from orchestrator.websocket import init_websocket_manager
from pydantic_forms.exception_handlers.fastapi import form_error_handler
from pydantic_forms.exceptions import FormException

logger = structlog.get_logger(__name__)

sentry_integrations: list[Integration] = [
    SqlalchemyIntegration(),
    RedisIntegration(),
    FastApiIntegration(),
    AsyncioIntegration(),
    ThreadingIntegration(propagate_hub=True),
]


class OrchestratorCore(FastAPI):
    graphql_router: Any | None = None

    def __init__(
        self,
        title: str = "The Orchestrator",
        description: str = "The orchestrator is a project that enables users to run workflows.",
        openapi_url: str = "/api/openapi.json",
        docs_url: str = "/api/docs",
        redoc_url: str = "/api/redoc",
        version: str = __version__,
        default_response_class: type[Response] = JSONResponse,
        base_settings: AppSettings = app_settings,
        **kwargs: Any,
    ) -> None:
        self.base_settings = base_settings
        websocket_manager = init_websocket_manager(base_settings)
        distlock_manager = init_distlock_manager(base_settings)
        self.broadcast_thread = ProcessDataBroadcastThread(websocket_manager)

        startup_functions: list[Callable] = [distlock_manager.connect_redis]
        shutdown_functions: list[Callable] = [distlock_manager.disconnect_redis]
        if websocket_manager.enabled:
            startup_functions.extend([websocket_manager.connect_redis, self.broadcast_thread.start])
            shutdown_functions.extend(
                [websocket_manager.disconnect_all, self.broadcast_thread.stop, websocket_manager.disconnect_redis]
            )

        super().__init__(
            title=title,
            description=description,
            openapi_url=openapi_url,
            docs_url=docs_url,
            redoc_url=redoc_url,
            version=version,
            default_response_class=default_response_class,
            on_startup=startup_functions,
            on_shutdown=shutdown_functions,
            **kwargs,
        )

        initialise_logging()

        self.include_router(api_router, prefix="/api")

        init_database(base_settings)

        self.add_middleware(ClearStructlogContextASGIMiddleware)
        self.add_middleware(SessionMiddleware, secret_key=base_settings.SESSION_SECRET)
        self.add_middleware(DBSessionMiddleware, database=db)
        origins = base_settings.CORS_ORIGINS.split(",")
        self.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=base_settings.CORS_ALLOW_METHODS,
            allow_headers=base_settings.CORS_ALLOW_HEADERS,
            expose_headers=base_settings.CORS_EXPOSE_HEADERS,
        )

        self.add_exception_handler(FormException, form_error_handler)  # type: ignore[arg-type]
        self.add_exception_handler(ProblemDetailException, problem_detail_handler)  # type: ignore[arg-type]
        add_exception_handler(self)

        @self.router.get("/", response_model=str, response_class=JSONResponse, include_in_schema=False)
        def _index() -> str:
            return "Orchestrator orchestrator"

    def add_sentry(
        self,
        sentry_dsn: str,
        trace_sample_rate: float,
        server_name: str,
        environment: str,
        release: str | None = GIT_COMMIT_HASH,
    ) -> None:
        logger.info("Adding Sentry middleware to app", app=self.title)
        if self.base_settings.EXECUTOR == ExecutorType.WORKER:
            from sentry_sdk.integrations.celery import CeleryIntegration

            sentry_integrations.append(CeleryIntegration())

        if self.graphql_router:
            sentry_integrations.append(StrawberryIntegration(async_execution=True))

        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=trace_sample_rate,
            server_name=server_name,
            environment=environment,
            release=f"orchestrator@{release}",
            integrations=sentry_integrations,
            propagate_traces=True,
            profiles_sample_rate=trace_sample_rate,
        )

    @staticmethod
    def register_subscription_models(product_to_subscription_model_mapping: dict[str, type[SubscriptionModel]]) -> None:
        """Register your subscription models.

        This method is needed to register your subscription models inside the orchestrator core.

        Args:
            product_to_subscription_model_mapping: The dictionary should contain a mapping of products to SubscriptionModels.
                The selection will be done depending on the name of the product.

        Returns:
            None:

        Examples:
            >>> product_to_subscription_model_mapping = { # doctest:+SKIP
            ...     "Generic Product One": GenericProductModel,
            ...     "Generic Product Two": GenericProductModel,
            ... }

        """
        SUBSCRIPTION_MODEL_REGISTRY.update(product_to_subscription_model_mapping)

    def register_graphql(
        self: "OrchestratorCore",
        query: Any = Query,
        mutation: Any = Mutation,
        register_models: bool = True,
        subscription_interface: Any = SubscriptionInterface,
    ) -> None:
        new_router = create_graphql_router(query, mutation, register_models, subscription_interface)
        if not self.graphql_router:
            self.graphql_router = new_router
            self.include_router(new_router, prefix="/api/graphql")
        else:
            self.graphql_router.schema = new_router.schema


main_typer_app = typer.Typer()
main_typer_app.add_typer(cli_app, name="orchestrator", help="The orchestrator CLI commands")

if __name__ == "__main__":
    main_typer_app()
